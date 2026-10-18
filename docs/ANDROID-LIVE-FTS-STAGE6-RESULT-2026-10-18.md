# Android local FTS — stage 6 result

## Implemented

- Codal sidecar schema v3 adds `codal_monthly_history_checkpoint` for each symbol:
  next page, observed result count, completed pages, oldest publication time,
  status, and last HTTP/error details. The migration is additive and safe to
  rerun; it preserves the existing raw-report and derived-value tables.
- `syncMonthlyHistory()` reads Codal search pages from the earliest supported
  date, with bounded work per invocation (default: one page and at most five
  newly fetched reports). The current Codal API was observed returning 20
  letters per page even when `Length=-1` is requested.
- Each page's new raw HTML, extracted monthly values, provenance, and checkpoint
  are committed together through the existing SQLite sidecar. A failed report
  leaves the checkpoint on that page; retry skips reports already stored by
  `TracingNo`, then continues. Network and inconsistent pagination outcomes
  remain retryable and do not mark history complete.
- `syncLatestMonthlySales()` remains the separate latest-report refresh path.
  Backfill does not overwrite its freshness state with the status of an older
  report.
- The Android local resolver exposes the backfill as
  `POST /api/codal/monthly-sales/history-sync?symbol=…`; optional `max_pages`
  and `max_reports` query limits are clamped by the sync service.

## Verification

- Unit coverage exercises additive migrations from schema versions 1 and 2,
  idempotent migration, future-schema refusal, page-bounded progress, resuming
  to completion, retry after a mid-page HTTP 429 without duplicate rows, and
  resolver method/limit handling.
- Targeted Vitest: 3 files, 29 tests passed.
- `npx tsc -b --pretty false` and targeted ESLint passed.
- These are mocked Codal-response tests. This stage did not make a network
  request from Android or prove Cache API persistence on a physical device.

## Not yet live FTS

Monthly-history completion is only a Codal pagination checkpoint. It does not
prove symbol identity/alias completeness, complete issuer scope, or correctness
of all five FTS inputs. `readMonthlyRevenueSeries()` therefore continues to
report `INCOMPLETE`, and the Android FTS/funnel resolvers remain snapshot-backed.
No UI or automatic background coordinator invokes the endpoint yet. No live FTS
result is claimed.

## Next

Expose this bounded sync through an explicit Android data-update action or a
safe background coordinator, report per-symbol progress/freshness, and verify
the sync on an emulator. Then establish identity and period coverage before
using monthly rows in the growth axis; keep the axis `NOT_EVALUATED` until its
desktop-parity fixtures pass.
