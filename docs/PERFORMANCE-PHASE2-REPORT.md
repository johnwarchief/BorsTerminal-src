# BorsTerminal — Performance Phase 2 Report

Branch: `mission/coder3-performance-resource-2026-10-22`
Phase 1 final recovered at `a4228cef`; Phase 2 rounds P2-R1 … P2-R6 are
committed on top of it. No push, merge, cherry-pick or migration was performed.
Coder1 (`api/execution.py`, broker/AutoClicker) and Coder2 (`api/chart.py`,
technical engine, `tools/ra365_*`, `frontend/src/features/technical/**`,
pattern detector/API/markers) files were **not modified**.

Environment: portable CPython 3.12.10 + uvicorn on 127.0.0.1:8000, Node 22.22.0,
Edge via playwright-core, `market.db` session 20261014, market **closed**,
`BORS_NO_FETCH_LOOPS=1`, `BORS_GZIP_LEVEL=1`. Browser samples use a fresh
context (empty client cache) unless stated; the server was warm. Heap readings
force CDP GC first. Samples are modest and reported honestly; expensive
workflows were not run 20–30 times.

## 1. What changed and what it bought

| Round | Change | Measured result |
|---|---|---|
| P2-R1 | Removed the full 6.8 MB `/api/market` and full `/api/screener` from the symbol path; inspector consumes the same FTS-plan query instead of a second `/api/fts`; trace gated until detail | FTS symbol switch median **≈6.9 s → 2.3 s**; switch bytes **136–515 KiB → 18 KiB**; one FTS request |
| P2-R2 | Funnel body cache keyed by request options **plus data signature** (30 s ceiling, engine TTL unchanged at 8 s); GET parity; `If-None-Match` for schema-less GETs; conditional LRU kept at 32 | POST P50 **146.0 → 57.9 ms**; conditional GET **16.9 ms / 0 B**; re-entry no longer rebuilds 13.4 MB |
| P2-R3 | In-flight raw GET dedupe in `shared/api/http.ts` (each caller still parses with its own Zod schema); strategy-tree probe | Technical open/switch now issues **one** `/api/chart` and **one** `/api/fts` (was two of each); tree open 1.0–1.3 s, actions 24–35 ms, DOM 663/248 |
| P2-R4 | Deliberate hover/focus (300 ms debounce) prefetches the dossier's `fts-plan` + `key-levels` under the same query keys; quick passes fire nothing | Same-symbol A/B: click→ready **1.05–2.23 s direct → 0.35–0.55 s** after hover (median ≈1.69 → ≈0.47 s); 2 requests either way; sweep 4 rows @120 ms → **0** requests |
| P2-R5 | Preserve `preset/chain/tech` when a funnel row opens the dossier (no second funnel key); final-view stage is `handover`; clear a resurrected symbol after back-to-funnel | Back retries **3/6 → 0/6**; max `/api/funnel` per cycle **5 → 2**; post-warm heap **49.5–61.7 MB with +10.2 MB jumps → 40.3–43.3 MB flat**; DOM/listeners flat |
| P2-R6 | Scoped screener asks for the active preset/chain and can skip the funnel gate (`gate=0`) where the consumer never reads it; final re-profile and reports | Scoped screener **0.6–2.6 s → 0.1–1.1 s per switch** (25 warm samples: p50 61 ms, p95 216 ms); final switch median **≈1.62 s** (range 1.07–1.79 s) with 8–10 requests / 9–16 KiB |

### Final FTS switch (6 samples, two symbols, fresh client cache, warm server)

| Sample | ready (click → dossier with `/api/fts` applied) | requests | bytes |
|---|---:|---:|---:|
| آبنوس | 1,674 / 1,246 / 1,794 ms | 9–10 | 10–16 KiB |
| آتش | 1,693 / 1,067 / 1,574 ms | 8–9 | 9–10 KiB |
| **median** | **1,624 ms** | **9** | **10–16 KiB** |

The remaining critical path is the Coder2-owned `/api/fts/<symbol>` (1.0–1.6 s
in these traces). `/api/fundamental/<symbol>` (0.5–1.4 s) and
`/api/chart/<symbol>/key-levels` (33–1,020 ms) overlap it; the scoped screener
is now **p50 61 ms / p95 216 ms** over 25 warm samples (per-switch samples
97–1,114 ms under contention). Request count and transfer are no longer the
problem.

### Funnel transport (P2-R2, rechecked after the P2-R6 restart)

`/api/funnel?preset=tech_first…` first 200: **1,396 ms / 13,429,057 B**.
Conditional GET: **304, 19 ms, 0 B**. After 9 s: **304, 118 ms, 0 B**.
25 conditional samples: **p50 33 ms, p95 153 ms, max 627 ms** (all 304/0 B).
A warm unconditional GET (body cache): **200, 103 ms, 13.4 MB**. The first full
fetch after the P2-R6 server restart took **6.15 s** while the body cache was
empty; that is a post-restart cost, not a steady-state number. The 13.4 MB raw
payload is the tech-first full stage set; responses after the first are
conditional or body-cached.

### Hover prefetch on the final build

| Symbol | direct click→ready | hover+click | prefetch lead | gain |
|---|---:|---:|---:|---:|
| آبنوس | 1,545 ms | 553 ms | 363 ms | 992 ms |
| آتش | 1,458 ms | 465 ms | 364 ms | 993 ms |

`requests = 2` in both modes; the prefetched request usually completes before
the click (`click→fts end` is negative). A 4-row sweep at 120 ms/row makes no
request; a 500 ms dwell makes exactly the two intended requests
(`hover-p2r4.json`, `hover-scan.json`, `hover-p2r6-final.json`).

### Strategy tree and technical workflow

- Strategy tree true open: **1.33 s** (P2-R3: 0.95–1.29 s; one sample here).
  In-tree actions 24–35 ms; DOM 663 nodes / 248 SVG, unchanged. No tree change
  was made.
- Technical traces still show one `/api/chart` and one `/api/fts` per open and
  per switch (P2-R3 dedupe intact). The technical page additionally fetches the
  full `/api/market` (1,220,692 B on the wire) from the protected
  `TechnicalPage.tsx:60`; this is handed to Coder2, not edited.
- Technical open/switch latency is still dominated by protected endpoints
  (`/api/chart` 0.2–5 s, `/api/fts` 0.7–1.6 s warm, first call on some symbols
  25–41 s). Details and reproduction: `docs/CODER3-PERFORMANCE-HANDOFF-TO-CODER2.md`.

### Startup (default FTS landing, warm server)

| Metric | Cold context | Warm reload |
|---|---:|---:|
| login | 1.10–1.82 s | — |
| funnel workspace shell | 3.43–4.31 s | 0.51–0.75 s |
| data-ready (`/api/funnel` + 2 frames) | 3.73–4.45 s (median ≈4.08 s) | 0.75–0.85 s |
| API requests / bytes | 3–4 / 8–13 KiB | 2–3 / 8 KiB |
| worst long task | 554–1,115 ms | not captured |

Cold startup is dominated by client JS/React work, not API traffic; the funnel
response itself was 20–190 ms in two runs and 190 ms/379 KiB in the third.
These are warm-server numbers; a cold-server startup was not measured.

### CPU, RAM and sustained session (final build)

- 10 s funnel idle: **150 ms** task CPU, **0 requests**, heap and DOM/listener
  deltas 0.
- 60 s idle: **805 ms** task CPU (≈1.3% of one core), **0 requests**, heap
  **+71 KiB**, nodes/listeners −2. Final 5 s: heap delta 0, DOM/listeners flat.
- Six FTS open/close cycles: 0 back retries, 672–1,350 ms CPU per cycle, 7–11
  requests, DOM 1,469 / listeners 286 flat. Heap after warm-up 35.6–52.9 MB in
  this run (one +16.5 MB GC-timing jump at cycle 4); the controlled P2-R5
  after-run was 40.3–43.3 MB with no jump vs 49.5–61.7 MB and +10.2 MB jumps
  before the duplicate-key fix.
- Three technical opens: 1.29–2.76 s CPU each (protected chart engine); chart
  DOM/listeners added on entry and released on leaving, no growth across cycles.
- Pattern-overlay toggles: **NOT_MEASURED** — the default technical view exposed
  no `pattern-toggle-*` control to the probe.

## 2. Correctness and regression coverage

- `dev/funnel_get_parity_v1.py` 2/2, `dev/funnel_signature_v1.py` 4/4,
  `dev/market_row_endpoint_v1.py` 4/4, `dev/screener_symbol_scope_v1.py` 7/7
  (including new `gate=0` parity: same indicators/vetoes, gate fields absent,
  `funnel_gate.state=skipped`; `gate=1` unchanged).
- Vitest on touched paths: funnel stages 37/37 (incl. URL-preservation test),
  hover prefetch 2/2, master/nav/funnel 57/57, inspector rail/glance/closed +
  screener gate + fundamental page + card contract: **73 passed, 3 failed** in
  the combined run. The 3 failures are in `fundamental-codal-poll.spec.tsx`
  (DB-status polling race/queue) and reproduce identically on the previous
  commit with the P2-R6 changes stashed — **pre-existing**, not introduced here.
  The same 20 inspector/screener tests pass when run individually.
- `tsc -b` 0 errors; production Vite build PASS.
- `dev/mstat_status_panels_contract_v1.py` remains 201/203 with the two
  `free_float`/`official_impact` failures proven pre-existing since `ef92c89c`
  in Phase 1. Full Python and full Vitest suites were not completed within the
  session budget (same blocker as Phase 1); they are **NOT_COMPLETED**, not
  claimed as passing.

## 3. Not measured / boundaries

- Live-session polling and freshness under an open market: **NOT_MEASURED**
  (market closed throughout). Cached/304 paths are labelled as such.
- Cold-server startup (restart + cache rebuild): **NOT_MEASURED**.
- Technical overlay toggles: **NOT_MEASURED** (no control exposed).
- Protected-endpoint internals (detector CPU vs serialization) could not be
  split; the handoff records endpoint-level timings and a reproduction.
- High-percentile FTS numbers rest on 6 samples; they are indicative, not a
  20–30-sample characterization.

## 4. Evidence index

| Path | Content |
|---|---|
| `artifacts/performance/phase2/workflows-baseline.json` / `workflows-p2r1*.json` | switch request/bytes baselines and P2-R1 |
| `artifacts/performance/phase2/fts-api-p2r2*.json` | funnel endpoint timings, GET/304 |
| `artifacts/performance/phase2/funnel-reentry-p2r2.txt` | 304/0-byte re-entry |
| `artifacts/performance/phase2/tech-trace.json`, `tech-trace-p2r3.txt` | technical request dedupe |
| `artifacts/performance/phase2/tree-final.json`, `tree-switch-baseline.json` | strategy tree |
| `artifacts/performance/phase2/hover-p2r4.json`, `hover-scan.json`, `hover-p2r6-final.json` | hover A/B and sweep guard |
| `artifacts/performance/phase2/resources*.json` | CPU/heap/DOM cycles and idle |
| `artifacts/performance/phase2/switch-trace-p2r6*.json` | final switch request/size/ready samples |
| `artifacts/performance/phase2/startup.json` | cold/warm FTS landing startup |
| `artifacts/performance/phase2/lowcost-samples.json` | 25-sample p50/p95 for conditional funnel GET and scoped screener |
| `artifacts/performance/phase2-results.csv` | machine-readable summary |
| `docs/CODER3-PERFORMANCE-HANDOFF-TO-CODER2.md` | protected-path handoff |

## 5. Retained / rejected

All six rounds retained a measured change. No optimization was rejected for a
regression. The hover trigger was deliberately moved from 180 ms to 300 ms so
ordinary pointer sweeps cannot fire expensive prefetches; the measured sweep
guard shows zero requests. The 30 s funnel body ceiling from P2-R2 remains a
freshness trade-off: the engine's own TTL is still 8 s and any in-process data
change changes the signature/key immediately.

The next highest-value work is not in Coder3's boundary: the first-call
`/api/fts` tail (25–41 s on some symbols) and the technical page's 1.2 MB
`/api/market` fetch. Both are specified in the handoff with reproduction steps.

## 6. Final validation and delivery (2026-10-23)

The branch was pushed and fast-forwarded to `main`. A full-suite validation was
then attempted on the merged code. It found four regressions that the targeted
P2 work had not caught; they were fixed in `558f8daa` before the final docs
commit:

| Area | Regression | Fix |
|---|---|---|
| notifications | source-health cache key used raw `MAX(publish_date)` | key on `COUNT(*) + MAX(rowid)` (both cheap; no raw date comparison) |
| funnel | body-cache signature used screener cache key/ts, so the warm race built two 7.5 MB bodies | use the scan payload's own `as_of` |
| screener | `gate=0` query parameter broke the "only preset/chain/symbols" contract and was a bypass door | restore the gated `/api/screener`; serve the inspector from `/api/screener/row`, which never emits `funnel_candidate` and reports `state=skipped` |
| mstat | idle/session TTL read `datetime.now()`, bypassing the SWR guard's injected clock and extending the test TTL to 300 s | read the module `time` and fall back to the session TTL |

Post-fix targeted results (all green): screener funnel gate 30/30, scoped
screener 7/7, funnel warm deadlock 7/7, funnel signature 4/4, funnel GET parity
2/2, market row 4/4, mstat SWR 16/16, mstat cache durability 4/4, notification
source cache 6/6, canonical publish date 24/24, screener/card parity PASS,
engine-path parity 7/7, materialized FTS results 109/109. The HTTP smoke shows
`/api/screener/row` returning one row with `funnel_gate.state=skipped` and no
`funnel_candidate`, while `/api/screener` remains `applied` with the flag.
TypeScript is clean and the production build passes.

Full-suite attempt, before the fixes: **163 OK / 15 FAIL / 1 skipped**. The 15
were: the four regressions above, three timeouts (confidence engine,
screener/card parity, engine-path parity — the two parity guards pass when run
alone), six `ModuleNotFoundError` failures caused by the portable Python's
`ignore_environment=1`/`safe_path=True` (all pass when `dev/` is placed on
`sys.path`), and two pre-existing failures (`repo hygiene` 122/123:
tracked-but-ignored PNGs under `_audit/`; `tsetmc_p0` 164/165). The full Python
suite was not rerun end-to-end after the fixes; the affected guards were rerun
individually. `confidence_engine_v973` did not finish even with a 28-minute
budget and remains **NOT_COMPLETED**.

Full Vitest attempt: stopped after **16/201** spec files because the suite was
not tractable in the session budget; the partial log has 435 passing test lines
and four `Test timed out in 5000ms` failures under CPU contention. The five
touched specs pass 94/94 when run alone. `fundamental-codal-poll` remains the
known 3-failure pre-existing file.

`mstat_status_panels_contract_v1` remains **201/203** with the same
`free_float`/`official_impact` failures reproduced against the baseline before
the P2-R6 changes. `fundamental-codal-poll.spec.tsx` remains 3 failures
(pre-existing, reproduced with P2-R6 stashed). Live-session behavior,
cold-server startup and technical overlay toggles remain **NOT_MEASURED**.

Delivery state: pre-merge `main` was `784d9d8a`; the Phase 2 branch
`mission/coder3-performance-resource-2026-10-22` ended at `2d4db99e` and was
pushed; `main` was fast-forwarded `784d9d8a..2d4db99e`. The regression-fix
commit is `558f8daa`; the final docs commit follows it. No history was rewritten
and no force push was used.

The two out-of-scope costs remain open and are unchanged by this work: the
first `/api/fts` call tail on some symbols (25–41 s) and the technical page's
full `/api/market` fetch (1,220,692 B); both are in the Coder2 handoff.
