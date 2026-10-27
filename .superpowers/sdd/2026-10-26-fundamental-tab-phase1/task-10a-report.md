# Task 10A report — monthly-only real companies in the FTS screening universe

## Status

DONE. Base `6e3292e1` on `mission/fts-indicator-engineering`; no branch switch,
no push. Task commit: `feat(fts): include monthly-only companies in the screening universe`
(the hash is the commit that contains this report; see the final response).

## Files

- `fts_engine.py` — `bulk_scan` universe only:
  - collect `ms_all` (every `monthly_sales.symbol`, normalized) with one extra
    `SELECT DISTINCT symbol` query;
  - iterate `set(annual) | {k for k in ms_all if k in board_of}` instead of
    `annual.keys()`;
  - no per-indicator formula, threshold, gate, or row-schema change. Monthly-only
    rows keep `ref=None`: i1 from the monthly series, i2 data-gap, i3 `None`
    (margin-class N/A unchanged), i4 via `annualize_rows(recs, fs_rev=0.0)`,
    potential `None` (no FS margin), `is_holding` still from `ind4_exempt`,
    path/label per Task 7, `sym_out` from `board_of`.
- `dev/test_fts_monthly_universe_v11.py` (new, temp DB) — production monthly-only,
  holding monthly-only, fund, instrument-less phantom, and a board company with
  no usable (positive-YTD) monthly series; card/scan/bulk parity for i1/i2/i3/i4,
  path, label and months.
- `dev/fts_screener_card_parity_v10.py` — monthly-only cohort (up to 3) selected
  from screener rows whose normalized key has no annual (`period_months>=12`)
  financial statement; asserts bulk vs `evaluate_v10` vs `scan_symbol` parity on
  i1/i2/i3/i4, acceptance path, annualization label/months, and that i3 is
  `None` in both engine paths. Cache invalidation now keeps `fts_results`
  untouched (`drop_materialized=False`) so the check does not DELETE from
  `market.db`; monthly-only rows missing from the materialized table fall back to
  live `evaluate_v10` in the existing loop.
- This report. `.superpowers/sdd/.gitignore` ignores `*`; the report was
  force-added per the task's explicit commit list.

Only these task files were staged. Pre-existing dirty files
(`_audit/RA365-LEDGER-RULE-2026-10-12.csv`, `dev/fixtures/fts_v10_payloads.json`,
`_audit/P5G-*`, `_audit/PHASE5F-*`) were left untouched.

## Why 785, not 784

The first implementation used only the existing `ms` map (rows with
`ytd_revenue > 0`) and produced **784** rows / 72 monthly-only companies. An
independent read-only count of all board-listed symbols with **any**
`monthly_sales` row and no annual FS gives **73**; the missing one is غنوش,
whose only monthly row has a negative YTD (`-62`), so the positive-YTD map
drops it. Since a monthly filing means «monthly-only company», `ms_all` was
added and the company enters as an honest data-gap row (`i1 None`, `i2` data
gap, `i3 None`, `i4 False`, no months/label, score 0) — no fake series. With
that, the measured 785 is reproduced exactly.

## Exact counts

All Python runs with `PYTHONIOENCODING=utf-8` and TMP/TEMP/SQLITE_TMPDIR on
`D:\BorsTerminal-tmp`.

| Command | Result |
| --- | --- |
| `python dev/test_fts_monthly_universe_v11.py` | `49/49 passed (with temp DB)` · `OK monthly-only universe` · exit 0 (red before the engine change: 7 failures / 15) |
| `python dev/fts_screener_card_parity_v10.py` | screener 785 · bulk 785 · checked 785 / mismatch 0 · index-4 785 (missing 0), both exempt 158 · scan sample 31 / divergence 0 · monthly-only 73, sample 3, divergence 0 · endpoint 785 / mismatch 0 / error 0 · `RESULT: PASS` · exit 0 |
| `python dev/test_fts_v10_ladder.py` | `57/57 passed` · exit 0 |
| `python dev/test_fts_ind4_v11.py` | `OK ind4 paths` · `51/51 passed` · `183/183 passed (with temp DB)` · exit 0 |
| `python dev/fts_defaults_parity_guard.py` | `78 checks, 0 failed` · `FTS DEFAULTS PARITY OK` · exit 0 |
| `python dev/test_fts_na_v11.py` | `fts-na: 41 pass / 0 fail` · exit 0 |
| `python dev/test_fts_margin_v11.py` | `OK margin tiers (pure)` · `74/74 passed` · `192/192 passed` · exit 0 |
| `cd frontend && npx tsc -b` | no output, exit 0 |

No existing test hard-coded 712/785; nothing needed updating.

## Read-only probe (`market.db` URI `mode=ro`)

```
bulk rows: 785
monthly-only rows: 73
  دلر    i1=True  i2=False (gap True) i3=None i4=True path=sales_to_mcap months=6 score=3 mcap=27.7 همت
  دالبر  i1=True  i2=False (gap True) i3=None i4=True path=sales_to_mcap months=6 score=3 mcap=26.0 همت
  دسبحان i1=True  i2=False (gap True) i3=None i4=True path=sales_to_mcap months=6 score=3 mcap=22.8 همت
  دسينا  i1=True  i2=False (gap True) i3=None i4=True path=sales_to_mcap months=6 score=3 mcap=22.5 همت
  فصبا   i1=True  i2=False (gap True) i3=None i4=True path=sales_to_mcap months=6 score=3 mcap=20.9 همت
  فنقره  i1=True  i2=False (gap True) i3=None i4=True path=sales_to_mcap months=6 score=3 mcap=11.9 همت

expected 73 missing from bulk: 0
phantom (no instrument) absent: 57 / 57 absent from bulk
fund-classified monthly symbols in the monthly-only set: 0 (the four
fund-classified monthly filers — مدیریت، وسکاب، وصندوق، ومدیر — are all absent
from bulk and were already kept out by the fund gate)
غنوش present: i1=None i2=False gap=True i3=None i4=False path=None label=""
```

The brief's “2 funds” do not appear among the monthly-only candidates in the
current DB (the fund-classified monthly filers above all carry annual FS under
an alternate spelling and were already excluded before 10A). No phantom name
entered. Insurer rows still enter only as companies and are excluded by their
separate risk gate.

## Notes / deferred

- The parity script's `get_screener()` path (via `funnel_engine`) rebuilds the
  existing derived `board_hist_v` / `board_hist_fv` tables, as it already does
  on every run. Our own probe and the new test use `mode=ro` / a temp DB; the
  script no longer drops `fts_results`.
- Live browser/RTL check of the fundamental tab was not run (backend-only task).
- No thresholds, gates, formulas or row schema were changed; no operational
  market data was written.
