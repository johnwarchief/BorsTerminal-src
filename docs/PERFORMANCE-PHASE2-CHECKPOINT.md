# BorsTerminal — Performance Phase 2 Checkpoint

Branch: `mission/coder3-performance-resource-2026-10-22`
Phase 1 recovered at `a4228cef` (all Phase 1 commits present).
Phase 2 status: **P2-R1 … P2-R6 complete.** Final report:
`docs/PERFORMANCE-PHASE2-REPORT.md`; machine-readable summary:
`artifacts/performance/phase2-results.csv`. No push/merge.
Environment/data: identical to Phase 1 (portable CPython 3.12.10, Node 22.22.0,
Edge, verified market.db session 20261014; market closed; loops disabled).

## Completed rounds

| Round | Status | Commit | Scope |
|---|---|---|---|
| P2-R1 | DONE | (this commit) | FTS symbol-switch request storm: single-row market, scoped screener, one FTS plan, gated trace |
| P2-R2 | DONE | (this commit) | Funnel data-signature cache, GET/304 transport, schema-less conditional cache |
| P2-R3 | DONE | (this commit) | strategy-tree verified; in-flight GET dedupe for technical/FTS outer layer |
| P2-R4 | DONE | (this commit) | end-to-end re-profile; deliberate-hover prefetch of the two protected per-symbol endpoints |
| P2-R5 | DONE | (this commit) | CPU/RAM/long-session; duplicate funnel key + back-navigation race fixed |
| P2-R6 | DONE | (this commit) | final balance: active-preset/gate-skipped scoped screener; final benchmarks and reports |

## P2-R1 measured result

Baseline symbol switch (same corrected browser harness, before change):
5.9 / 10.0 / 7.9 / 3.3 s → median ≈6.9 s. After: 1.3–4.5 s across 6 samples
(median ≈2.3 s, −67%); switch API bytes 136–515 KiB → **18 KiB** (median
−76%). Request count 6–11 → 7–9, but the oversized ones are gone:

- full `/api/market` (6.8 MB raw / 1.2 MB gzip) removed from the symbol path;
  `/api/market/row` is ~0.8 KB and 30–200 ms with ETag/304.
- full `/api/screener` (1.2 MB / 122 KB gzip) replaced by
  `/api/screener?symbols=<sym>` (~2 KB response).
- duplicate `/api/fts/<symbol>` removed: inspector now uses `useFtsPlan`, the
  same query key as MasterPage; the protected `useFtsAnalysis` file is
  untouched and still owns the technical feature.
- eager `/api/funnel/trace` removed until the inspector detail page opens.

Warm FTS re-entry in the corrected harness: 0.62–0.67 s. Cold FTS (fresh
browser, warm server): 3.1–4.9 s. Strategy tree (4.75–4.85 s) and technical
switch (~5.3 s) are unchanged and remain P2-R3 targets; technical is
Coder2-owned/read-only.

## P2-R2 measured result

The FTS funnel body is 7.5 MB raw / 388 KB gzip. Repeated polls/entries rebuilt
it because the engine/body TTL was 8 s while the UI polls every 20 s. After:

- server body cache is keyed by the request options **plus a data signature**
  (market revision/static/day, screener cache identity, tech-context ts) and
  cached for up to 30 s; the engine `_run` TTL stays 8 s, so screener freshness
  is unchanged;
- the UI requests `/api/funnel` by GET with the same options and benefits from
  `If-None-Match`; a 6.5 s leave/return now returns **304 with 0 bytes** instead
  of a 388 KB/7.5 MB 200. Schema-less GETs are now ETag-cached (bounded LRU);
- GET and POST produce the same body for simple and
  `exceptions`/`strategy_settings` inputs (guard), and the signature changes
  with revision/screener/tech inputs (guard).

Endpoint P50 (warm): POST 146.0 → **57.9 ms**; GET 59.1 ms; conditional GET
16.9 ms / 0 bytes. Browser warm re-entry after 6 s: 304, no body parse. The
30 s body ceiling is recorded as a freshness trade-off; any in-process data
change changes the key immediately.

## P2-R3 measured result

- Strategy-tree true open: 0.95–1.29 s; page-zone switches 48–109 ms; zoom
  controls 19–69 ms; 663 DOM nodes / 248 SVG nodes; heap stable at 24.8 MB.
  The earlier 4.8 s number was a harness wait for an already-cached registry.
  No tree layout change was needed.
- Technical outer layer: identical concurrent GETs are now merged in
  `shared/api/http.ts` at the **raw JSON** level, then each caller applies its
  own Zod schema. A technical open/switch previously made two `/api/chart` and
  two `/api/fts` calls; the trace now shows one of each
  (`tech-trace-p2r3.txt`, `http-inflight-dedupe.spec.ts`). The protected
  endpoint latency remains: handoff written to
  `docs/CODER3-PERFORMANCE-HANDOFF-TO-CODER2.md`.
- Technical open 2.4–3.7 s, switch ~5.3 s; unchanged and protected-bound.

## P2-R4 measured result

Re-profiling the complete FTS journey after R1–R3 left one unowned cost: every
row click mounts the dossier and immediately asks the protected server for
`/api/fts/<symbol>` and `/api/chart/<symbol>/key-levels`. The FTS strategy tab
is a table of 1,017 candidates; a user typically rests on a row before
clicking. P2-R4 overlaps that dwell with the two requests.

Implementation (`FtsFunnelAllStages.tsx:StageRow`): hover/focus starts a 300 ms
debounce; when it fires, `queryClient.prefetchQuery` warms `fts-plan` and
`key-levels` with **the same query keys** the dossier uses, so the click
subscribes to the in-flight/complete query instead of starting a duplicate.
Quick pointer passes cancel the timer; no new endpoint or second engine.

Same-symbol A/B (6 pairs: آبنوس ×3 direct-first, آتش ×3 hover-first; each
measurement in a fresh browser context so the client cache is empty; server
pre-warmed once per symbol so both modes see the same backend state):

| Metric | Direct click | Deliberate hover + click | Gain |
|---|---:|---:|---:|
| click → dossier with `/api/fts` applied | 1.05–2.23 s (median ≈1.69 s) | **0.35–0.55 s** (median ≈0.47 s) | 0.58–1.86 s |
| click → FTS response end | 0.99–2.19 s | −0.17…+0.32 s (usually already done) | 0.67–2.36 s |
| requests per switch | 2 (`fts`, `key-levels`) | 2 (started during dwell) | 0 extra on click |
| prefetch lead at 650 ms dwell | 0 | 363–381 ms | — |

Sweep guard (network events counted at request start): moving the pointer over
4 rows at 120 ms each produced **0** requests; a 500 ms dwell produced exactly
the two intended requests (`artifacts/performance/phase2/hover-scan.json`).
Unit coverage: `fts-hover-prefetch.spec.tsx` 2/2 (deliberate fires, quick pass
does not); funnel Vitest 36/36; `tsc -b` 0 errors; production build PASS.

The re-profile also found a protected-endpoint tail that the earlier P50 hid:
the **first** `/api/fts/<symbol>` call is 25.5–40.6 s for some symbols
(آرامش 37.9 s, آرمان 36.8 s, آس 40.6 s, آسا 25.5 s), while the same warm symbol
answers in 0.7–1.2 s. Prefetch cannot remove that first-call cost; it is added
to the Coder2 handoff with the measured symbols.

## P2-R5 measured result

Workloads (one warm session, Edge/CDP `Performance.getMetrics` +
`Memory.getDOMCounters`, GC forced before every heap reading; market closed):
10s funnel idle, 6 repeated FTS dossier open/close cycles, 3 technical chart
opens, pattern-overlay toggles, 60s sustained funnel idle. Raw numbers:
`artifacts/performance/phase2/resources.json` (before) and
`resources-after2.json` (after); scripts `phase2_resource_probe.js`.

Idle baseline: 10s on the funnel cost 0.11–0.25s of task CPU, **0 requests**,
0 DOM/listener delta, flat heap. The 60s idle also made 0 requests; final 5s
heap delta 0 KB, nodes/listeners unchanged. This is the expected closed-market
rhythm (`sessionPollMs`), not a disabled poll: the same request path is used
during market hours.

Two real defects showed up only under repeated open/close:

1. **Duplicate funnel key on the dossier.** Row clicks built the dossier URL as
   `/master/<sym>?stage=<stage>` and dropped `preset`/`chain`/`tech`. When the
   URL preset differed from the saved preset (a shared/bookmarked link, or the
   probe's `?preset=tech_first`), MasterPage's dossier recomputed the whole
   funnel with a different key: an extra `/api/funnel` (7.5 MB raw), a second
   parsed model, and **+10 to +25 MB JS heap** that survived GC. Fix: preserve
   the current query string on pick (only `stage` replaced, `symbol` removed),
   and the final-view active stage is `handover` instead of the stale snapshot
   (`FtsFunnelAllStages`). The dossier now shares the funnel model the user was
   looking at — same four-gate position, no second payload.
2. **Back-navigation race.** `master-open-funnel`/`master-back` clear the symbol
   and navigate; `SymbolInspector`'s route→store sync could then run with the
   stale `routeSymbol` and resurrect it. In the probe this needed a retry in
   **3 of 6** cycles, each retry producing extra `/api/funnel` and calendar
   requests. Fix: if the route has no `:symbol` shortly after an explicit
   back-to-funnel, clear the resurrected symbol (`MasterPage`).

After both fixes (same 6-cycle workload):

| Metric | Before | After |
|---|---:|---:|
| cycles needing a back retry | 3 / 6 | **0 / 6** |
| `/api/funnel` calls per cycle (max) | 5 | 2 (1 background refetch) |
| heap after warm-up | 49.5 → 61.7 MB (jumps of +10.2 MB) | 40.3–43.3 MB (no jump) |
| dossier first-open heap delta | +25.3 MB | +17.8 MB (single funnel model) |
| DOM nodes / listeners per cycle | 1,469–1,471 / 286 | 1,469 / 286 (flat) |

Technical (Coder2-owned, read-only): each open adds ~136 listeners and chart
DOM (485 listeners / 1,737 nodes on first open); they are released on leaving
and do not grow across 3 cycles. Technical task CPU 1.6–6.2 s per open
(chart engine, protected). Pattern-overlay toggles were **NOT_MEASURED** — the
default technical view exposed no `pattern-toggle-*` control to the probe.
60s idle task CPU was 1.2 s (before) / 3.4 s (after, single sample) with 0
requests and a flat final heap; not claimed as an improvement.

Correctness: funnel Vitest 37/37 (incl. new URL-preservation test), hover 2/2,
master + nav-history + funnel 57/57, `tsc -b` 0 errors, production build PASS.

## P2-R6 measured result

The final re-profile showed one more server-side waste: the inspector's scoped
`/api/screener?symbols=<sym>` ran `_funnel_gate` with the default preset for
every dossier open, recomputing a full funnel (0.6–2.6 s CPU) for one row while
`/api/fts` was running. The panel never reads the gate fields
(`tape_status/technical_status/fundamental_status/gate_state/funnel_candidate`).
The hook now sends the active `preset`/`chain` and `gate=0`; the server skips
`_funnel_gate` but keeps the assembly veto and all five indicators. Default
`gate=1` is unchanged for other consumers.

| Metric | Before P2-R6 | Final |
|---|---:|---:|
| scoped screener latency | 0.6–2.6 s | **0.1–1.1 s** (137–190 ms in the warm pair) |
| FTS switch click→dossier | median ≈1.69 s (P2-R4 direct) | **median 1.62 s** (range 1.07–1.79 s, 6 samples) |
| requests / bytes per switch | 7–10 / 9–16 KiB | 8–10 / 9–16 KiB |
| funnel conditional GET | 19 ms / 0 B | **19 ms / 0 B** (after 9 s: 118 ms / 0 B) |
| FTS landing cold data-ready | — | 3.73–4.45 s (median ≈4.08 s; login 1.10–1.82 s) |
| FTS landing warm reload | — | **0.75–0.85 s** |
| 60 s funnel idle | — | 805 ms task CPU, 0 requests, heap +71 KiB, DOM/listeners flat |
| 6 open/close cycles | 3/6 back retries (P2-R5 before) | 0 retries, 672–1,350 ms CPU/cycle, 7–11 requests, DOM 1469 / listeners 286 |

Strategy tree final: open 1.33 s, in-tree actions 24–35 ms, DOM 663/248
(unchanged code). Technical: one `/api/chart` + one `/api/fts` per open/switch
(dedupe intact); the protected page still requests the full `/api/market`
(1.22 MB on the wire) — added to the Coder2 handoff. Technical open CPU
1.3–2.8 s, chart DOM/listeners release on leave. Overlay toggles NOT_MEASURED
(no control exposed).

Correctness: `dev/screener_symbol_scope_v1.py` 7/7 (new gate=0 parity checks);
funnel GET/signature 2/2 + 4/4; market-row 4/4; `tsc -b` 0; build PASS; touched
Vitest 73 passed / 3 pre-existing failures in `fundamental-codal-poll.spec.tsx`
(reproduced on the previous commit with P2-R6 stashed). Full Python/Vitest
suites remain NOT_COMPLETED.

## Correctness coverage run

- `dev/market_row_endpoint_v1.py` — 4/4 PASS (same p_closing, ETag/304,
  unknown stays null).
- `dev/screener_symbol_scope_v1.py` — 4/4 PASS (symbol-scoped row == full
  row; unknown empty).
- Inspector/screener Vitest — 92/92 PASS (after updating mocks from full-board
  cache to the new single-row query; no assertions removed).
- Master/tape Vitest — 68/68 PASS.
- `npx tsc -b` 0 errors; production `npm run build` PASS.
- P2-R2: `funnel_get_parity_v1` 2/2, `funnel_signature_v1` 4/4, funnel
  Vitest 59/59, http conditional tests 7/7.
- P2-R3: in-flight dedupe Vitest 1/1; strategy-tree probe and technical trace
  recorded under `artifacts/performance/phase2/`.
- Persian glyph guard 4/4; `struct_check` PASS.

## Kept / not touched

- Kept: all Phase 1 commits and reports; no push/merge.
- Protected files untouched: `api/chart.py` (including `/api/fts/{symbol}` and
  `/api/patterns/{symbol}`), `frontend/src/features/technical/**`,
  `tools/ra365_*`, `api/execution.py`, broker adapters.
- The inspector now *consumes* the same protected FTS endpoint through the
  master hook instead of mounting a second protected hook; no protected code
  was edited.

## Next steps

No Coder3-owned performance work remains. The two largest remaining costs are
protected/owned elsewhere: the first-call `/api/fts` tail (25–41 s on some
symbols) and the technical page's full `/api/market` fetch. Both are recorded
with reproduction steps in `docs/CODER3-PERFORMANCE-HANDOFF-TO-CODER2.md`.
Live-session behaviour, cold-server startup and technical overlay toggles remain
NOT_MEASURED.
