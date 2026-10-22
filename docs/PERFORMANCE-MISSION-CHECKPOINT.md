# BorsTerminal — Performance Mission Checkpoint

Mission: Coder3 performance & resource engineering, 2026-10-22
Branch: `mission/coder3-performance-resource-2026-10-22`
Base commit: `784d9d8a` (origin/main at clone time)
Status: **six rounds implemented and committed; final validation in progress**

## Current position

| Round | Status | Commit | Scope |
|---|---|---|---|
| 0 — baseline | DONE | `784d9d8a` | environment, 30-sample API baseline, real-browser baseline, profile |
| 1 — runtime bottleneck | DONE | `1147447a` | mstat snapshot single-flight + boot panel warm-up |
| 2 — backend/DB | DONE | `77d32d90` | notifications source-health cache by DB content key |
| 3 — frontend/interaction | DONE | `cf9c0048` | TEDPIX direct response + content ETag/304 |
| 4 — end-to-end | DONE | `e250b325` | light closes map; palette feed gated to open state |
| 5 — CPU/memory | DONE | `e8bfcf07` | schema checks once per schema_version; LRU ETag cache |
| 6 — resource/balance | DONE | `941be7c0` | session-aware mstat TTL + board-first warm-up re-key |
| harness methodology | DONE | `98bc436a` | direct DOM click (removed a 6s false delay) |

Machine: Windows 10 Pro 19045 x64, 8 GB RAM. Runtime: portable CPython
3.12.10, Node 22.22.0, Edge Chromium. Data: verified `data-latest`
`market.db` (session 20261014, 6,022 board rows). Backend measured with
`BORS_NO_FETCH_LOOPS=1`, gzip level 1, port 8000. Market was closed; live
session polling is **NOT_MEASURED**.

## Current best results (same workload, same machine)

| Metric | Baseline | Best | Δ |
|---|---:|---:|---:|
| market-status first open, 3 cold servers (median) | 10,020 ms | 3,827 ms | −61.8% |
| market-status first open, probe pass0 | 10,795 ms | 7,812 ms (single-flight only) | −27.6% |
| notifications source panel p50 (30) | 342.9 ms | 22.3 ms | −93.5% |
| TEDPIX 200-path p50 (30) | 171.2 ms | 43.9 ms | −74.4% |
| TEDPIX repeat conditional p50 (30) | 171.2 ms | 5.43 ms / 0 B | −96.8% |
| landing encoded API payload (median of 3) | 1,235 KiB | 43 KiB | −96.5% |
| get_db CPU per 300 connections | 2.03 s | 1.53 s | −24.6% |
| post-idle (60 s) market-status first open | 7,043 ms | 4,333 ms | −38.5% |

Resource evidence: sustained 6-cycle session kept DOM nodes (4,278) and JS
listeners (844) flat and heap plateaued ≈34 MB; 60 chart-symbol switches grew
post-GC heap only 27.8 → 28.2 MB. Backend idle outside session: 0.48 s renderer
task time / one 31 KB closes poll in 60 s. Encoded payload for a landing fell
from ~1.2 MB to ~43 KiB.

## Tests actually run

- `dev/mstat_snapshot_cache_v1.py` — 10/10 PASS
- `dev/mstat_snapshot_singleflight_v1.py` — 4/4 PASS
- `dev/notifications_sources_cache_v1.py` — 6/6 PASS
- `dev/test_notifications_v1.py` — 30/30 PASS
- `dev/market_index_etag_v1.py` — 8/8 PASS
- `dev/stale_wiring_v1073.py` — 19/19 PASS
- `dev/market_closes_v1.py` — 5/5 PASS
- `dev/get_db_schema_once_v1.py` — 6/6 PASS
- `dev/mstat_cache_durability_v1.py` — 4/4 PASS
- `dev/persian_glyph_guard.py` — 4/4 PASS
- Frontend `npx tsc -b` — 0 errors; `npm run build` — PASS
- Targeted Vitest: pipeline/palette/status/conditional/LRU — 39/39 PASS
- `dev/mstat_status_panels_contract_v1.py` — 201/203; the two failures are
  **PRE_EXISTING** on HEAD (`free_float` expected by the guard, engine emits
  `official_impact` since `ef92c89c`; proven by `git show HEAD:...` grep)
- Full `python dev/run_all_tests.py` — see final report for the recorded
  outcome; run with both dev servers closed.

## Kept / reverted / not attempted

- Kept: all six round commits, LRU ETag bound (preventive; no measured leak
  because chart responses carry no ETag), boot warm-up re-key.
- Reverted inside Round 6: including the SQLite WAL file mtime in the mstat
  cache key. SQLite creates/deletes `-wal` per connection, so the key changed
  every request and the cache never hit (measured 8.5 s). The key is back to
  the four data markers; TTL is session-aware.
- Rejected after A/B: moving `PRAGMA journal_mode=WAL` out of per-request
  setup — no measurable benefit (6.29 vs 6.31 ms p50).
- Not attempted (documented as next work): wiring all MarketStatusPage panels
  to the existing `/api/mstat/board` single request; live-session funnel
  polling changes; chart endpoint (Coder2-owned); execution path (Coder1).

## Ownership boundaries respected

No edits to `api/chart.py`, `frontend/src/features/technical/**`,
`tools/ra365_*`, `api/execution.py`, broker adapters, execution tests/reports,
or RA365 artifacts. Chart/CDN latency is reported read-only as a remaining
bottleneck.

## Next action

Finalize `docs/PERFORMANCE-SIX-ROUND-REPORT.md`, commit the evidence matrix and
reports, confirm the working tree, and do not push or merge into `main`.
