# Task 10B2a2 report — batch names, parity coverage, cleanup handoffs

- Base: `6fef2ab8`; branch `mission/fts-indicator-engineering`; no branch switch,
  no push.
- Commit: `fix(fts): batch names, parity coverage and cleanup handoffs`
  (the hash is the commit containing this report; see the final response).
- Scope: backend parity/cleanup only. No threshold, formula or gate semantics changed.
  The one engine behavior change is the documented card↔bulk net-margin substitute
  (below), which makes bulk/scan match the card contract.

## Files

- `fts_engine.py`: `i4_potential_margin` helper; bulk/scan use a separate
  `pot_margin`/`margin_basis` for indicator 4 only; bulk/scan emit
  `i4_available`/`i4_exempt`/`i4_na`/`i4_reason` and (bulk) `margin_used_pct`/
  `margin_basis`; scan emits `i3_reason` and the same i4 fields; fund gating for the
  i4 path; `NON_COMPANY_TOKENS` normalized at import; unused `sym` removed.
- `api/fundamental.py`: `v10_batch` builds one `company_name_map` and passes
  `company_name=` + returns `company_name`; `ind4_valuation` raises a clear
  `KeyError` when neither threshold key exists; card i4 is N/A for funds (Task 7 M6);
  stale header/identity comments fixed.
- `dev/fts_screener_card_parity_v10.py`: full 3-way comparison of
  `gross_margin`/`i3`/`i4` numbers and N/A fields/reasons for all 785 rows; scan is
  run for all rows with prebuilt market maps; i3 failure tuple fixed; monthly cohort
  minimum asserted.
- `dev/test_fts_ind4_v11.py`: pot_min loud-failure and `potential_min` tests; fund
  temp-DB row (no fabricated path); `v10_batch` name-only-holding test; unused test
  constants removed.
- `dev/test_fts_monthly_universe_v11.py`: stale expectation repaired (a data-gap
  `i3_reason` is now populated by Task 10B2a1; `i3_na` still means class N/A only).
- `dev/fund_not_applicable_v1028.py`: stale docstring (it compares the card, not
  `company_profile`).
- `frontend/.../FtsDrillDown.tsx`: dead `drilldown-i4-annualize` secondary-label
  markup removed (it could never render).

## Fix 1 — `v10_batch` company name

- One `fts_engine.company_name_map(conn)` per batch; `company_name=` is passed to
  `evaluate_v10` and echoed in every output row.
- The name is also the identity signal for sector-less companies. Read-only probe:
  **26** symbols have `instruments.sector_name = ''` and a non-empty company name;
  before the fix all 26 evaluated as `non_company`/«FTS ندارد». After: 26/26 named,
  **0** «FTS ندارد». (The brief said 16; the current bank has 26 name-only
  identities, and 11 bulk rows have no name at all but all 11 have a non-empty
  sector, so they stay valid companies.)
- Temp-DB test: a holding with empty sector and name «شرکت سرمایه گذاری شنام» must
  not be «FTS ندارد», and its row must carry the name.

## Fix 2 — parity extension and the net-margin substitute

The card (`ind4_valuation`) uses a **net-margin substitute** when the gross margin is
N/A and `ref.net_profit/ref.revenue ∈ (0,100]`: `margin_basis="net_margin_proxy"`,
`margin_used_pct` = net margin, and a potential is computed. Bulk/scan set
`margin=None` and produced no potential. Before the fix the read-only probe found
**64** rows diverging only on `potential_pct` (e.g. `زفكا`: card 26.0 vs bulk None;
`زقيام` 20.0 vs None; `زبينا` 16.0 vs None).

Fix: `fts_engine.i4_potential_margin(margin, ref)` mirrors the card's condition. Its
result is passed **only** to `gross_profit_potential` for indicator 4; `gross_margin`,
`i3_pass`/`i3_na`/`i3_reason`, the score and `sector_filter` continue to use the
unmodified gross margin. Bulk/scan now publish `margin_used_pct`/`margin_basis`
(`net_margin_proxy` when substituted) and the i4 N/A fields. `scan_symbol` now also
publishes `i3_reason`/`i4_reason`, so the reasons are compared, not skipped.

The parity script now compares, for every one of the 785 rows:

- `gross_margin`, `i3` (tri-state), `i3_na`, `i3_reason`;
- `i4` (tri-state), `i4_na`, `i4_exempt`, `i4_available`, `potential_pct`,
  `margin_basis`, `margin_used_pct`, `i4_reason`, `acceptance_path`;
- all three surfaces: bulk `bulk_scan` row, card `evaluate_v10`, `scan_symbol`
  (full scan with prebuilt `m141`/liquidity/`no_sales`/sessions maps).

The old monthly `i3` failure appended a 3-tuple and crashed the print loop; it is a
2-tuple now. The monthly cohort asserts at least 3 rows, so a reverted universe
cannot pass vacuously.

Result: **785 rows, 0 mismatches, 0 field divergences, scan sample 31/0, monthly
73 rows / 3 sample / 0, endpoint 785 / 0 / 0, RESULT: PASS**.

## Fix 3 — `pot_min` loudness

`ind4_valuation` now reads `potential_min`, else `profit_potential_min`, else raises:

```
KeyError: ind4_valuation: neither 'potential_min' nor 'profit_potential_min'
is present in thresholds; refusing to invent a 40% floor
```

Both keys remain supported; the test covers both and the loud failure.

## Fix 4 — cleanups

- `NON_COMPANY_TOKENS` is normalized once at import; `classify_identity` no longer
  normalizes per token and no longer assigns an unused `sym`.
- `dev/fund_not_applicable_v1028.py` docstring now says it compares `evaluate_v10`
  (the card), not `company_profile`.
- Dead drill-down secondary-label markup removed; its existing tests assert absence.
- Task 7 M6: a synthetic operating fund (FS revenue + huge mcap, `has_operating_sales
  = 1`) is now gated to i4 N/A in the card and `scan_symbol` (`identity kind == fund`
  / `fund_class_match`), so it cannot get `sales_to_mcap`. Production exposure was
  zero (all funds are already exempt); the new temp-DB row and the 785-row parity
  confirm no score change.

## Fix 5 — parser suspects (documentation only, no parser change)

Phase 2 ingest items:

- **`ثجوان`** — tracing `1442601` (period `1404/06/31`): revenue 2,291,695 MRL,
  `gross_profit` NULL; the same symbol’s tracing `1614940` (`1405/06/31`) has
  `gross_profit` 2,849,058 at revenue 2,849,058. Expected field: `gross_profit` for
  `1442601`; verify the CODAL label (the neighbour row’s GP == revenue, so this is a
  manual-check pointer, not a confirmed parser bug).
- **`دكوثر`** — tracing `1566740`: revenue/operating_profit/net_profit = 1/1/1 and
  `gross_profit` NULL. Expected real values; check the unit/column parse before any
  margin is published.

## Verified counts (all exit 0)

| Check | Result |
| --- | --- |
| `python dev/test_fts_na_v11.py` | **57 pass / 0 fail** |
| `python dev/test_fts_margin_v11.py` | **80/80** and **205/205** |
| `python dev/test_fts_ind4_v11.py` | **53/53** and **216/216** (with temp DB) |
| `python dev/test_fts_v10_ladder.py` | **57/57** |
| `python dev/test_fts_monthly_universe_v11.py` | **49/49** (with temp DB) |
| `python dev/test_fts_sector_v11.py` | **47/47** |
| `python dev/fts_defaults_parity_guard.py` | **78 checks, 0 failed** |
| `python dev/fts_screener_card_parity_v10.py` | **785 rows, mismatch 0, field divergence 0**; PASS |
| `python dev/fund_not_applicable_v1028.py` | **25 pass / 0 fail** |
| `python dev/persian_glyph_guard.py` | **4 passed / 0 failed** |
| `cd frontend && npx tsc -b` | exit 0 |
| `npx vitest run src/__tests__/fts-drilldown.spec.tsx src/__tests__/fts-fundamental-labels.spec.tsx` | **2 files / 56 tests passed** |

## Read-only probes (market.db, 785 rows)

| Probe | Result |
| --- | --- |
| Parity, all three surfaces | 0 mismatches; 0 field divergences |
| `net_margin_proxy` rows | **64** (all now identical card/bulk/scan; e.g. `زفكا` potential 26.0, margin_used 39.2, i3 `None`/`i3_na=False`, i4 `True`) |
| `v10_batch` name-only identities | 26/26 named, 0 «FTS ندارد» |
| Bulk rows with empty company name | 11; every one has a non-empty sector, so identity is unaffected |
| Fund path | synthetic operating fund: card/scan i4 `None`, `available=False`, no potential/sales ratio |
| `pot_min` both keys missing | loud `KeyError` shown above |
| `i3_na` on bulk | remains class-N/A only (data gaps `False`); parity compares `i3_pass is None` against the card’s `ind3_na` |

## Notes / deferred

- `dev/test_fts_monthly_universe_v11.py` had one stale assertion at base: after
  Task 10B2a1, a no-FS production row gets a non-empty data-gap `i3_reason`; the test
  still expected `""`. It now asserts the card’s same reason and keeps `i3_na=False`.
- Live browser/RTL rendering was not run (Task 10 owns the live check).
- Full `python dev/run_all_tests.py` was not run (Task 10 gate).
- The materialized `fts_results` path remains empty; the new bulk fields are
  available for it but it was not populated.
- Pre-existing dirty `_audit/*` and `dev/fixtures/fts_v10_payloads.json` were left
  untouched and unstaged.
