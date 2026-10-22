# Coder3 → Coder2 — Performance Handoff: protected FTS/chart endpoints

Date: 2026-10-22 · Phase 2, after P2-R3
Repository/branch inspected: `mission/coder3-performance-resource-2026-10-22`
at `bd975653` + P2-R3 working tree.
Coder3 did **not** modify any protected file. This is a measured handoff.

## 1. Workload and reproduction

| Item | Value |
|---|---|
| Symbol | `فولاد` first open, then switch to `خودرو` (and other mainwatch symbols) |
| Routes | `#/technical/<symbol>` (chart + analysis), `#/master/<symbol>` (FTS dossier) |
| Data | verified market.db session 20261014 (market closed) |
| Backend | `BORS_NO_FETCH_LOOPS=1 BORS_GZIP_LEVEL=1 python -m uvicorn app:app --port 8000` |
| Browser trace | `node tools/performance/tech_request_trace.js` → `artifacts/performance/phase2/tech-trace.json` |
| FTS endpoint baseline | `python tools/performance/phase2_fts_api.py` → `artifacts/performance/phase2/fts-api-baseline.json` |
| Flow benchmark | `node tools/performance/phase2_fts_probe.js --runs 2` |

## 2. Evidence: protected endpoints dominate

Measurements after Coder3 removed duplicate in-flight GETs (P2-R3):

- `/api/fts/<symbol>` (`api/chart.py:4232`): first 1.0–2.5 s; **P50 870 ms**,
  P95 2.06 s over 10 warm samples. Under a symbol-switch burst it was
  2.6–4.7 s.
- `/api/chart/<symbol>` (`api/chart.py:1059`, route resolved by the technical
  hooks): 0.5–5 s depending on CDN/cache state; response ~1.1 MB (فولاد).
- `/api/chart/<symbol>/key-levels` (same protected module): 4.5 ms warm but
  first calls under a switch 0.5–8.8 s.
- Technical workflow open: 2.4–3.7 s; symbol switch ~5.3 s (stable across
  repeats). Strategy-tree and FTS outer-layer work does not move these.
- Coder3's in-flight response dedupe now makes the technical page issue one
  `/api/chart` and one `/api/fts` request instead of two of each
  (`tech-trace-p2r3.txt`); further gains require the protected endpoints.

## 3. Hot path / where time goes

`api/chart.py::_fts_analyze_symbol` already has a process-local cache with a
key built from symbol, timeframe, last close, entry hint, price basis, `as_of`,
build/ruleset and hourglass settings (TTL 900 s). Yet the observed P50 is
~870 ms warm, so either:

1. the key includes a value that changes on every request (e.g. `as_of` or
   `entry_hint`), forcing a miss; or
2. the cache is not shared across the `get_chart_db`/`/api/fts` call paths used
   by the UI, or the first computation happens inside the request before the
   cache entry is stored.

The chart route additionally performs CDN retrieval/repair when its local
cache is cold; that part is network-bound and should be reported separately
from detector/analysis CPU.

This phase could not split detector CPU vs. serialization because the timing
is inside the protected function; the endpoint-level split above is the
available evidence.

## 4. Narrow proposed optimization (hypothesis, for the owner)

- Audit the `_fts_analyze_symbol` cache key on consecutive identical
  `/api/fts/فولاد` calls. If `as_of`/`entry_hint` are request-derived, key only
  on the **data basis** and slice candles per `as_of` at read time; otherwise
  warm calls should be near-zero cache lookups instead of ~870 ms.
- Add an ETag/`If-None-Match` (304) on the single-symbol FTS and chart
  responses, keyed by the same data signature already used by the analysis
  cache. Coder3's `http.ts` already stores ETags and will reuse the parsed
  body; no frontend technical change is required.
- For chart cold loads, expose whether the response came from local cache or
  CDN (`source`/`degraded` already exists in the payload) so the user-visible
  split is measurable without guessing.
- Do not change trend/CHoCH/Fib/pattern semantics or no-lookahead slicing;
  `as_of` must remain a real historical cutoff.

**Expected outcome (hypothesis, not measured):** warm `/api/fts/<sym>` from
~870 ms to <50 ms and remove a repeated ~1.1 MB chart body on re-open, with
identical payloads. Verify before claiming.

## 5. Tests that must protect the change

- `dev/fts_engine_paths_parity_v1076.py` (five-axis path parity)
- `dev/indicator_math_v1074.py` (MA/RSI/last-closing oracle)
- `dev/technical_*`/`chart_*` guards and `api/chart.py` contract tests
- A new test: same symbol + same data basis + same `as_of` ⇒ byte-identical
  payload; changed basis/config/build ⇒ different ETag/cache key; a historical
  `as_of` never sees candles after that date.
- Coder3 will run only read-only profiling of these tests; no protected edits.

## 6. What Coder3 already changed around this boundary

- Symbol switch no longer pulls the 6.8 MB board / full screener / duplicate
  FTS-plan requests from the outer UI (P2-R1).
- Funnel `GET`/304 and data-signature cache (P2-R2); no FTS rules changed.
- In-flight raw-response dedupe for identical GETs (P2-R3); chart/FTS bodies
  are still parsed with each caller's own schema, so no schema bleed.

## 7. P2-R4 addendum — first-call tail on `/api/fts/<symbol>`

Measured 2026-10-22 on the same session/dataset, direct HTTP (no browser), after
the P2-R4 re-profile:

| Symbol | First call | Second call |
|---|---:|---:|
| آرامش | 37,857 ms | 842 ms |
| آرمان | 36,807 ms | — |
| آس | 40,598 ms | 1,215 ms |
| آسا | 25,507 ms | — |
| آبنوس | 637 ms | 753 ms |
| آتش | 777 ms | 735 ms |

The first call for some symbols is 25–41 s; the same symbol then answers in
~0.7–1.2 s. That shape points at a cold, per-symbol computation/cache fill in
the protected path (not at repeated warm reads), and it is far above the
previous P50 870 ms. It directly affects the FTS funnel: clicking one of these
rows blocks the dossier for half a minute on first use, and no outer-layer
prefetch can hide it (P2-R4's deliberate-hover prefetch only moves the start;
the request still runs).

Please treat this as the top protected-path item:

1. Identify which per-symbol step takes the 25–41 s only on first call
   (chart/CDN fetch + repair, candle resample, or detector run) and whether the
   result is cached under a key that survives the call.
2. If it is cold computation, precompute it during the existing background
   technical scan (`funnel_tech_scan`) instead of inside the user request, or
   expose a readiness/progress contract so the UI can say "computing" instead of
   blocking; Coder3's UI already has a scan-progress slot it can consume.
3. Keep the same trend/CHoCH/Fib/pattern semantics and no-lookahead slicing.

Reproduction: `node -e "http.get('http://127.0.0.1:8000/api/fts/'+encodeURIComponent('آرامش'),...)"`
against the session-20261014 database; or open `#/master?preset=tech_first&stage=technical`
and click the آرامش row in a fresh server process. The P2-R4 browser A/B and
sweep evidence are in `artifacts/performance/phase2/hover-p2r4.json` and
`hover-scan.json`.
