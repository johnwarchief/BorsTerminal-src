# BorsTerminal — Performance Phase 2 Baseline (2026-10-22)

Continuation branch: `mission/coder3-performance-resource-2026-10-22`
Recovered HEAD: `a4228cef` (Phase 1 complete: `1147447a`, `77d32d90`,
`cf9c0048`, `e250b325`, `e8bfcf07`, `941be7c0` + docs/harness commits).
Machine/runtime/data: unchanged from Phase 1 — Windows 10 x64, 8 GB RAM,
portable CPython 3.12.10, Node 22.22.0, Edge Chromium, 1366×768, verified
`data-latest` market.db (session 20261014). Backend started with
`BORS_NO_FETCH_LOOPS=1`, gzip level 1, port 8000.
Market was closed; all live-session behaviour is `NOT_MEASURED`.

## 1. How this baseline was taken

| Harness | Purpose |
|---|---|
| `tools/performance/phase2_fts_api.py` | FTS/funnel/related GET+POST endpoint timings, bytes, ETags |
| `tools/performance/phase2_fts_probe.js` | browser workflow: cold/warm FTS, symbol dossier, same-symbol reopen, strategy tree, technical open/switch, 5 enter/leave cycles |
| `tools/performance/phase2_request_trace.js` | exact request waterfall (method, URL, response time) for one symbol switch |

`phase2_fts_probe` was corrected during P2-R1: the first cold measurement waited
for API entries after login and sometimes timed out. The baseline switch
numbers below come from the always-direct-click, response-timed harness and are
directly comparable to P2-R1; the cold/warm figures marked *preliminary* used
the earlier timing and are not used for an improvement claim.

Screener cache state: cold rebuild at first server start (≈4–6 min, because
`fts_results` is empty and `.screener_cache.json` had expired at 12 h). After
the rebuild, warm screen ≈0.36 s P50. This cold-screener cost is recorded, not
optimized here.

## 2. FTS endpoint baseline (warm server, 30 samples unless noted)

| Endpoint | First | P50 | P95 | Raw / gzip |
|---|---:|---:|---:|---:|
| `/api/funnel/registry` | 121 ms | 13.9 ms | 17.8 ms | 25,293 / 7,688 B |
| `/api/funnel/trace?symbol=فولاد` (10) | 1,074 ms | 9.4 ms | 14.3 ms | 2,500 / 1,159 B |
| `/api/fts/فولاد` (10, **Coder2-owned**) | 1,036 ms | **870.1 ms** | 2,061.7 ms | 28,455 / 7,768 B |
| `/api/fts/config` | 11.5 ms | 6.8 ms | 27.4 ms | 1,121 / 620 B |
| `/api/chart/فولاد/key-levels` (10) | 3.4 ms | 4.5 ms | 10.0 ms | 661 B |
| `/api/market/closes` | 131 ms | 56.4 ms | 188.2 ms | 78,512 / 31,130 B |
| `/api/screener` (10) | 1,340 ms | 361.8 ms | 925.3 ms | 1,203,781 / 122,598 B |
| `POST /api/funnel` (default UI body, 10) | 132 ms | **146.0 ms** | 988.5 ms | **7,574,466 / 388,054 B** |

`POST /api/funnel` has an ETag; a conditional POST returns **412** today (no
304), and the UI does not send `If-None-Match` on POST. Its body cache TTL is
8 s, while the UI polls every 20 s — so most polls rebuild the body/engine.

## 3. FTS browser workflow baseline

Corrected cold/warm/browser measurements (2 runs; direct DOM navigation):

| Workflow | Baseline |
|---|---:|
| Cold FTS funnel (fresh context, after login) | 5.2 / 7.5 s *(preliminary harness)* |
| Warm funnel re-entry | 3.7 / 4.4 s *(includes a 2.5 s harness timeout wait)* |
| Symbol switch to sparse sample | **5.9 / 10.0 s** (median ≈6.9 s) |
| Same-symbol reopen (cached plan) | 0.63 / 0.77 s |
| Strategy tree open (true direct-open) | 0.95 / 1.29 s; page switches 48–109 ms; zoom 19–69 ms |
| Technical chart open | 2.5 / 7.2 s (external chart/CDN bound) |
| Technical symbol switch | 5.3 / 5.4 s |
| Repeated dossier open/close (5×) | 0.30–0.65 s each |

### Symbol-switch request waterfall (one trace, before P2-R1)

All requests started within ~2 ms of each other; Chrome's six-connection limit
serialized them into five waves:

| Request | Rows/response | Response time |
|---|---:|---:|
| `/api/watchlist`, `/api/market`, `/api/selection/portfolio`, `/api/calendar/upcoming` | — | 0.3–0.6 s |
| `/api/fts/<sym>` **×2 duplicate calls** | 28 KB each | 2.9 s / 5.2 s |
| `/api/chart/<sym>/key-levels` | 661 B | 2.9 s |
| `/api/fundamental/<sym>` | 20 KB | 3.1 s |
| `/api/screener` **full universe for one row** | 1.2 MB / 122 KB gz | 4.6 s |
| `/api/funnel/trace` | 2.5 KB | 4.2 s |
| `/api/market` **full board for one row** | 6.8 MB / 1.2 MB gz | 0.6–5 s |
| `/api/tape-history` | 0.4 KB | 1.3–3.2 s |

Confirmed duplication/over-fetch: two `/api/fts/<sym>` calls (MasterPage
`useFtsPlan` + SymbolInspector's protected `useFtsAnalysis`), the full market
board and the full screener for single-row consumers, and an eager trace
request from a detail page that was not open.

## 4. Strategy tree and technical baseline

- Strategy tree is a client-side model/registry + SVG/canvas workspace. A
  direct-open measurement (no harness wait) is 0.95–1.29 s; page-zone switches
  are 48–109 ms and zoom controls 19–69 ms. The earlier 4.8 s figure was a
  harness wait for a registry request that was already cached, not app time.
- Technical open/switch is dominated by the protected chart endpoint
  (`/api/chart/<sym>`, 0.5–5 s, external/CDN-sensitive) and the protected
  `/api/fts/<sym>` analysis (~0.8–2 s warm). No Coder3 code was changed in
  Phase 2 baseline; these are read-only measurements.
- Pattern endpoint available in the checkout: `GET /api/patterns/{symbol}` in
  `api/chart.py` (**Coder2-owned**). It is measured read-only in P2-R3/R4; no
  detector/chart edits are permitted.

## 5. Constraints and labels

- Market closed; live freshness/polling is `NOT_MEASURED`.
- Baseline endpoint numbers are local-data measurements; external CDN
  variance is reported separately (technical chart/TEDPIX).
- No operational DB writes or migrations; all probes are read-only.
- Raw evidence: `artifacts/performance/phase2/`.
