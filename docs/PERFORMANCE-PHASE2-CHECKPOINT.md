# BorsTerminal — Performance Phase 2 Checkpoint

Branch: `mission/coder3-performance-resource-2026-10-22`
Phase 1 recovered at `a4228cef` (all Phase 1 commits present).
Phase 2 status: **P2-R1 complete; P2-R2 … P2-R6 pending.**
Environment/data: identical to Phase 1 (portable CPython 3.12.10, Node 22.22.0,
Edge, verified market.db session 20261014; market closed; loops disabled).

## Completed rounds

| Round | Status | Commit | Scope |
|---|---|---|---|
| P2-R1 | DONE | (this commit) | FTS symbol-switch request storm: single-row market, scoped screener, one FTS plan, gated trace |
| P2-R2 | NEXT | — | FTS computation/request orchestration; funnel cache/transport; secondary-panel priority |
| P2-R3 | pending | — | strategy-tree layout/readiness + technical outer layers |
| P2-R4 | pending | — | end-to-end FTS/technical integration |
| P2-R5 | pending | — | CPU/RAM/long-session |
| P2-R6 | pending | — | final resource balance/report |

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

## Correctness coverage run

- `dev/market_row_endpoint_v1.py` — 4/4 PASS (same p_closing, ETag/304,
  unknown stays null).
- `dev/screener_symbol_scope_v1.py` — 4/4 PASS (symbol-scoped row == full
  row; unknown empty).
- Inspector/screener Vitest — 92/92 PASS (after updating mocks from full-board
  cache to the new single-row query; no assertions removed).
- Master/tape Vitest — 68/68 PASS.
- `npx tsc -b` 0 errors; production `npm run build` PASS.
- Persian glyph guard 4/4; `struct_check` PASS.

## Kept / not touched

- Kept: all Phase 1 commits and reports; no push/merge.
- Protected files untouched: `api/chart.py` (including `/api/fts/{symbol}` and
  `/api/patterns/{symbol}`), `frontend/src/features/technical/**`,
  `tools/ra365_*`, `api/execution.py`, broker adapters.
- The inspector now *consumes* the same protected FTS endpoint through the
  master hook instead of mounting a second protected hook; no protected code
  was edited.

## Next experiment (P2-R2)

Profile the remaining symbol-switch burst with the new trace: plan/key-levels
(protected) vs secondary inspector panels (fundamental card, tape history,
calendar, portfolio). Measure whether deferring the optional fundamental card
until idle (the rail already has a screener fallback + pending notice) lowers
contention and switch time. In parallel, measure the funnel POST
payload/rebuild cadence; if evidence supports it, add a conditional/lightweight
revision path **without changing freshness**. Preserve parity; commit only
measured wins.
