# Task 10B1 report — read-only CODAL fundamental accuracy audit

## Status

DONE. Base `22c081ec` on `mission/fts-indicator-engineering`; no branch switch,
no push, no production-code change, no parser change.

- New: `dev/codal_fundamental_audit.py`
- Audit output: `_audit/codal-fundamental-audit-2026-10-28.md`
  (untracked by design; **not staged**)
- This report: force-added (`.superpowers/sdd/.gitignore` ignores `*`)
- Commit: `test(fts): add read-only CODAL fundamental accuracy audit`
  (the hash is the commit containing this report; see the final response)

## Read-only proof

- Every connection to `market.db` is
  `sqlite3.connect("file:...?mode=ro", uri=True)` plus `PRAGMA query_only=ON`.
- No helper that opens a writable connection internally is used for writes;
  `fts_results`, screener caches and fixtures were not touched.
- Measured DB signature before **and** after the run:
  size `242491392` bytes, `mtime_ns` `1793138745648018900` → **UNCHANGED**.
- `git status` shows the audit output as untracked; only the script and this
  report are staged.

## Command and result

```bash
export PYTHONIOENCODING=utf-8 TMP='D:\BorsTerminal-tmp' TEMP='D:\BorsTerminal-tmp' SQLITE_TMPDIR='D:\BorsTerminal-tmp'
python dev/codal_fundamental_audit.py
```

Exit **0**; `RESULT: PASS — no hard sanity failure; gaps reported honestly.`
Runtime ~4.4 s. `python -m py_compile dev/codal_fundamental_audit.py` is clean.

## Measured counts

| Measure | Measured |
| --- | ---: |
| bulk rows | 785 |
| strict real companies | 785 |
| candidate symbols (annual ∪ monthly-only board) | 1037 |
| annual-FS candidates | 964 |
| monthly-only candidates | 73 |
| excluded non-companies | 134 |
| — `no_instrument` | 133 |
| — fund/non-operating token | 1 |
| excluded funds | 118 |

The ledger's 153 non-companies does **not** reproduce on today's bank:
964 annual candidates = 712 table companies + 118 funds + 134 non-companies.
133 of the 134 are annual filers with no instrument/sector, not funds.

### Strict gaps

| Cohort | EPS < 3y non-consolidated | margin (production i3 None) | monthly (production, no monthly report) |
| --- | ---: | ---: | ---: |
| all 785 rows | 76 | 110 | 20 |
| 712 annual-FS rows (old universe) | 11 | 58 | 20 |
| 73 monthly-only rows | 65 | 52 | 0 |

Delta vs the ledger's 11 / 59 / 20: EPS **+65**, margin **+52** vs the measured
annual cohort, monthly **+0**. The 712-row cohort reproduces 11 EPS and 20
monthly exactly. Margin is **58, not 59**: `وهور` now resolves to holding via
`company_name_map` («گروه سرمایه گذاری …») and takes class N/A for i3, so it
is no longer a data gap. Net vs the ledger's 59 is **+51** (52 monthly-only
additions − 1 reclassification). Measured sugar contribution to the margin gaps
is 1 (`نيشكر`) and detergent is 1 (`شوينده`); both are annual-cohort rows, not
part of the monthly-only delta.

Monthly nuance: 20 production rows have no monthly report; **0** are
`i1_pass=False`, **20** are `i1_pass=None`. The ledger's 20 is the
«no monthly report» population; the brief's «i1 False» variant measures 0
because the engine honestly returns N/A when no series exists.

Consolidated-only EPS evidence: **331** strict rows carry
`eps_consolidated=True` (the ledger's ~226 production cases are included).

## Provenance / sanity sample

**36** real companies: production 5, bank 5, insurance 5, service 5, holding 5,
consolidated-only 5, monthly-only 5, non-bank financial 1. **69** FS rows and
**7** monthly rows checked.

- Hard failures: **0** (no production/service negative revenue, no
  `gross_profit > revenue`, no future period, no missing `tracing_no`).
- Soft issues: **31** — 30 × `basis_flag_mismatch` (title says «تلفیقی» but
  `is_consolidated=0`; live engines filter by title, so no indicator effect)
  and 1 × empty `unit`/`unit_norm` (`شپدیس`, older row; revenue/GP checks pass).
- `tracing_no`, `url`, `publish_date` present for every sampled FS row;
  revenue > 0 and EPS/net sign checks pass for every sampled row except the
  documented N/A/empty cases.

## Margin triage (all 110 strict margin gaps)

| Category | Count | Notes |
| --- | ---: | --- |
| `no_annual_fs` | 52 | all monthly-only production rows |
| `no_gross_profit` | 55 | revenue > 0, `gross_profit` NULL; 55/55 also carry `operating_profit` |
| `no_revenue` | 1 | `شارپیلن`, revenue NULL |
| `unit_suspicious` | 1 | `دكوثر`, revenue/op/net = 1/1/1 sentinel |
| `parser_suspect` | 1 | `ثجوان` |
| `class_na` | 0 | by construction (only production is counted) |

Representative raw rows:

| Symbol | Category | tracing_no | Period | Revenue (mrl) | Gross profit | Unit |
| --- | --- | ---: | --- | ---: | ---: | --- |
| زفکا | no_gross_profit | 1557526 | 1404/12/29 | 32,499,876 | NULL | mrl |
| زقیام | no_gross_profit | 1529261 | 1404/12/29 | 28,222,749 | NULL | mrl |
| شارپیلن | no_revenue | 1546450 | 1404/12/29 | NULL | NULL | mrl |
| دكوثر | unit_suspicious | 1566740 | 1404/12/29 | 1 | NULL | mrl |
| ثجوان | parser_suspect | 1442601 | 1404/06/31 | 2,291,695 | NULL | mrl |
| دلر | no_annual_fs | 1615226 (monthly) | 1405/06/31 | 83,344,583 YTD | — | monthly |
| دالبر | no_annual_fs | 1605328 (monthly) | 1405/06/31 | 91,649,643 YTD | — | monthly |

### Parser-suspect list (follow-up only; parser NOT changed)

- **ثجوان** — tracing `1442601` (1404/06/31) has revenue 2,291,695 and
  `gross_profit` NULL; tracing `1614940` (1405/06/31) of the same symbol has
  `gross_profit` 2,849,058 at revenue 2,849,058. Expected field:
  `gross_profit` for `1442601`; verify the CODAL label against the existing
  `سود(زیان)ناخالص` patterns. Caveat: the neighbour row's GP == revenue
  (zero COGS), so this is a manual-check pointer, not a confirmed parser bug.
- **دكوثر** — tracing `1566740` has revenue/operating_profit/net_profit = 1/1/1
  and `gross_profit` NULL. Expected real `revenue`, `gross_profit`,
  `operating_profit`, `net_profit`; check the unit/column parse before any
  margin is published.

The 55 `no_gross_profit` rows (all with `operating_profit` present) are recorded
as review candidates, not claimed parser bugs; offline evidence is insufficient
to distinguish «line absent in CODAL» from «parser missed it» for each.

## وملت — newest-period-only evidence (owner acceptance)

- FS-growth-path rows compared old vs new: **10**; rows that differ: **2**;
  rows whose **state** changes: **1** (`وملت`).
- `وملت` bulk: i1 N/A, i2 N/A (consolidated-only), i3 N/A (holding class),
  i4 N/A (holding exempt); EPS `[466, 307, 1478]`.
- `وملت` card (`evaluate_v10`): i1 N/A, i2 N/A, i3 N/A, i4 N/A; same EPS.
- Newest non-consolidated interim: 1404/12/29 (3m, revenue 6,596). Its
  prior-year row is 1403/12/30 (3m, revenue 5,196); interim matching is
  exact-day, so no pair is used. All annual rows are consolidated by title.
- New result: `fs_unavailable` → i1 = N/A.
- Old rule (fallback to first period with a pair): 1404/06/31 (9m) vs
  1403/06/31 (9m) = **+10.27%** → i1 = False. The row now shows an honest gray
  N/A instead of a stale-period growth. Bulk and card agree on the state; the
  card projects `passes` to bool (False) with `na=True`, bulk keeps `None`.
- Second numerically affected row, no state change: **وپسا** — old interim pair
  1405/03/31 (3m) = **288.61%**; new newest interim 1405/06/31 has no
  non-consolidated pair → annual 1402/12/29 = **178.79%**; both PASS.
- Hence the ledger's «exactly one live row» is true for the **state** change
  (`وملت`), while two rows change numerically. No policy was changed.

## Representative checks

15 symbols printed with indicator states and raw inputs (EPS series, margin
period/revenue/gross profit, annualized sales, mcap, i4 path): `فملی`, `فارس`
(production), `وبملت`, `وپاسار` (bank), `بپاس`, `البرز` (insurance), `رمپنا`,
`اخابر` (service), `شستا`, `تاپیکو` (holding), `فولاد`, `نوری`
(consolidated-only), `وشهر`, `وپخش` (monthly-only), `رکیش` (financial).
Full table is in the audit output; examples: `رمپنا` 4/5 with
`sales_to_mcap` path; `فولاد` 3/5; `وشهر` monthly-only 1/5 with i1/i2/i3/i4
N/A and annualized sales 169,748.7 bt.

## Notes / deferred

- No parser, threshold, formula, threshold config or production code changed.
- `fts_results` was not touched; no screener cache was invalidated.
- `financial_statements.is_consolidated` disagrees with the title-derived basis
  on **665** annual rows (e.g. `وملت` title says «تلفیقی», column is 0). The
  live engines filter by title, so indicator 3 / EPS / FS growth are unaffected;
  this is a provenance defect for a later data task.
- Negative operating revenue is a known CODAL convention for
  financial/holding companies and is reported as a soft gap; no production or
  service reference row has negative revenue.
- Pre-existing dirty files (`_audit/RA365-LEDGER-RULE-2026-10-12.csv`,
  `dev/fixtures/fts_v10_payloads.json`, untracked `_audit/P5G-*` and
  `_audit/PHASE5F-*`) were left untouched and unstaged.

## Commit scope

Staged exactly:

- `dev/codal_fundamental_audit.py`
- `.superpowers/sdd/2026-10-26-fundamental-tab-phase1/task-10b1-report.md`

Not staged: `_audit/*` (including the generated report), `market.db`, fixtures,
caches.
