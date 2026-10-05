# TSETMC P0 — Consumer Integration (1405-07-13)

Round: canonical P0 data → real consumers in BorsTerminal.
No parallel computation, no FTS logic change, no budget change.

Commits (staged as required, each with its own test run before commit):

| # | commit | what |
| --- | --- | --- |
| 1 | `65ad58f` | canonical/API wiring into the board row (+ two positional-insert fixes, single-source DDL) |
| 2 | `fadf1a0` | chart event markers in both engines (presentation only) |
| 3 | `21de16d` | Symbol Inspector regulatory section |
| 4 | `e88a732` | Technical sidebar / verdict-tab context, still no new verdict |
| 5 | `48ec3a2` | native-coverage measurement report tool |
| 6 | `4730d5f` | fix: the after-hours tick read the `MW_COLS` tail with `w[-2]/w[-1]` (see §1b) |

Predecessor: `cf28e44` (the canonical layer itself), `f204749` (gap matrix), `da22b2c` (PDF audit).

---

## 1) What existed with no consumer (measured, not assumed)

| data | producer | consumer before this round | status after |
| --- | --- | --- | --- |
| `client_type_value` (4 monetary values + `kind`) | `test_tsetmc.refresh_client_type_values` | only `mstat_engine.money()` (native-first) | provenance now reaches the board row (`ctv_kind`) and is readable in Inspector details |
| `price_adjust_events`, `share_change_events` | `fetch_corporate_events` (4 requests/run) | **none** — nothing read those tables | chart markers (both engines) |
| `instrument_state` (492 rows, 228 distinct instruments) | `fetch_state_and_notices` | **none** | board row `st_*` → Inspector + sidebar chip |
| `supervision_state` (17 rows) | same | **none** | board row `sup_*` → Inspector + board badge |
| `stop_reasons` (25 rows, keyed by `l_val18`) | same (webgw) | **none** | board row `stop_*` → Inspector + board badge |
| `tsetmc_messages` (600 rows, 2026-01-11 … 2026-10-05) | same | **none** | still none — see §11 |
| `instruments.isin`, `c_gr_val_cot` | `_mw_row` (`insID`, `cGrValCot`) | **none** | deliberately still none (see §2) |
| `market_watch.flow`, `p_red_tran`, `buy_op` | `_mw_row` (`flow`, `pRedTran`, `buyOP`) | **none** | deliberately still none |
| `tape_history.q_tot_cap` | writer fixed this round (named insert) | **none** | still none; column now fills correctly on upgraded DBs |

Live measurement of the two "free P1" groups (one `GetMarketWatch` request, repo writer,
`_mw_row` applied to the real payload): `insID` 3854/3854, `flow` 3854/3854,
`cGrValCot` 3854/3854, `buyOP` 844/3854, `pRedTran` 327/3854 non-empty; tuple length
equals `len(MW_COLS)` (36) and `len(_INST_COLS)` (13).

**But this machine's DB shows all five as NULL** (`instruments.isin` 0/5669 at the start
of this round; `market_watch.flow` 0/5669). Cause: the last full-board write to this DB
came from a build whose writer did not include those columns — `INSERT OR REPLACE` with a shorter
named column list nulls the rest. It is not a mapping bug; it self-heals the first time
this code performs the board sync. Not verified as healed in a released build yet.

Writer proof, in-memory, no network (`_mw_row` → `_MW_INSERT` / `_INST_INSERT` on a
fresh `create_schema` DB, one synthetic raw row with `flow=3, pRedTran=990, buyOP=1010,
insID='IRB5AG9207C1'`):

```
market_watch: ('K1', 3, 990.0, 1010.0, 100000000.0, 'tse_board_calc')
instruments : ('K1', 'IRB5AG9207C1', 'N4', None)
```

So the five columns are written correctly by this code; the NULLs observed in
`market.db` belong to a *different build writing the same DB file* on this machine
(a second backend was listening on 127.0.0.1:8002 throughout this round; port 8003 was
mine). During this round `instruments.isin` went from 0 to 3809 non-null while
`market_watch.flow` stayed 0 — consistent with two writers, not with a mapping bug.
Unverified: which build wins the last write on this machine, and whether the release
build leaves flow populated (needs one full sync from the released EXE).

## 1b) Bug found and fixed while wiring (would have shipped)

Appending `flow/p_red_tran/buy_op` to the end of `MW_COLS` silently moved the negative
indices used by the after-hours tick in `test_tsetmc.py`:

```python
w[-2], w[-1]   # was market_cap, market_cap_src — after the append: p_red_tran, buy_op
```

Every after-hours `UPDATE market_watch` would have written NAV prices into
`market_cap`/`market_cap_src`. Fixed in `4730d5f` by reading the tail through a
name→index map (`_MWI = {name: i for i, name in enumerate(MW_COLS)}`), with three guard
checks: the shape of the `MW_COLS` tail, the literal `"w[-2], w[-1]"` absent from the
source, and `market_cap` resolved from `_MWI`. Not yet observable as damage: the
after-hours branch only runs inside the tick, and `market_cap_src` in the current DB is
still 100% text.


## 2) What is available but deliberately not surfaced

`isin`, `flow`, `p_red_tran`, `buy_op`, raw `q_tot_cap`, `corporateTypeCode` stay in the
canonical layer only. Guard evidence: `dev/tsetmc_p0_v1076.py` asserts they never enter
`_BOARD_SQL` or the serialized body ("body must stay the same").

Reasoning per the brief: ISIN/NAV fields have **no consumer today**. The Inspector
diagnostic idea was measured against cost — adding `i.isin` to the board body would put
13 bytes on all 5669 rows (≈90 KB) for a field one panel might show, and the existing
`_DROP_FIELDS`/body-identity discipline already refuses unread keys. Also, `isin` is
currently NULL in real DBs (see §1), so surfacing it would have shown "-" everywhere.
The key that stop-reason lookups need (`l_val18`) is already resolved in SQL.

## 3) Provenance (`native | mixed | reconstructed`)

- Computed **once, in the writer** (`parse_client_type_value`) and stored as
  `client_type_value.kind`. SQL only reads it; `COALESCE(cv.kind,'reconstructed')` is the
  single place where "no row" becomes a word. UI never re-derives it from the four
  columns.
- Board payload: `ctv_kind` on every row (151,740 bytes raw of 4.91 MB; gzipped body
  612 KB — the string repeats, so the wire cost is small).
- Visibility: **only** the Inspector "جزئیات" expander. No badge, no column, no warning
  strip. It does not enter any verdict, filter, or FTS path (see §12 guards).
- Reconstructed is never presented as native: the label is explicit
  («بازسازی: حجم × میانگینِ وزنی»), and absence of a row means reconstructed, never
  "clean".

Known transient: a DB created by `cf28e44` has rows whose `kind` is NULL (the column
came after those writes). They are labelled `reconstructed` until that symbol is refetched
— the error direction is a false *warning*, not a false claim of authority. Budget 600/day
means refetch coverage is partial, so this can persist for days; measured as an open item
(§11), not fixed by a re-derivation in SQL.

## 4) Chart integration

`api/chart.py::_corporate_events(symbol)` reads the two canonical tables and returns:

```json
{"date": "2026-06-30", "type": "priceAdjust|shareChange",
 "from": <raw close | shares old>, "to": <adjusted close | shares new>,
 "source": "tsetmc_price_adjust_by_flow | tsetmc_share_change_by_flow"}
```

- Attached to the **existing** responses only: `/api/chart/{symbol}` (CDN path), its local
  fallback, and `/api/chart-db/{symbol}`. No new endpoint (`dev/tsetmc_p0_v1076.py` counts
  the three attachment sites).
- `type` comes from **which table** the row is in, never from `corporateTypeCode`
  (undecoded; see §11).
- Presentation only. The adjustment chain (`_adjust_events_from_rows`,
  `_factors_from_events`, `applyAdjustmentToCandles`) is untouched and never sees these
  rows, because the two `ratio` definitions differ: source table = «adjusted ÷ raw of the
  same day», chain = «today's base ÷ yesterday's close». Guard asserts no
  `_factors_from_events(...)` call mentions corporate events.
- One mapping for both engines: `frontend/src/features/technical/lib/corpEvents.ts`
  decides type → letter/colour/tooltip. `KLineChartWrapper` draws it into the existing
  `fts_corp_actions` group (row offsets 46/70 so it never hides under the chain marker at
  24), `FtsEngineChart` draws it through the engine interface as `kind: 'marker'` in group
  `fts-corp-events`. A day with no candle gets no marker (no invented position).
- The sidebar/verdict chips reuse the same mapping
  (`recentCorpEvents` + `corpEventChipLabel`), not a second translation.

Live read-back (repo code against this machine's DB): `فولاد` 14 events,
`شبندر` 7, `خگستر` 6, `وپستا` 0, unknown symbol → `[]`.

## 5) Symbol Inspector

`frontend/src/features/market/components/RegulatoryState.tsx`, mounted right after the
price line (hierarchy: current status → important event → details). One line plus a
`جزئیات` expander; compact, no card.

- Shows: current instrument state (`st_title` + raw `st_code`), stopped state and its
  start date, supervision with its reason count and the actual reason texts, and the
  timestamp of that state change (`st_d`, `st_h` → Jalali date + time).
- Four distinct renderings, asserted by tests:
  `data-regulatory-state="stopped|supervised|state|none|unavailable"`.
  `موردی ثبت نشده` ≠ `سالم` ≠ `متوقف`; `اطلاعات در دسترس نیست` is used only when the row
  itself is missing, and a feed error stays on the existing `inspector-feed-error` banner
  (not repeated).
- All folding/matching stays in the backend: `stop_reasons` joins on `i.l_val18` inside
  `_BOARD_SQL`; the frontend only uses the shared `findBoardRow` normalizer that the rest
  of the app already uses. No new fetch (props only; the test asserts `fetch` isn't called).
- Messages are **not** shown per symbol — see §11.

## 6) Market UI

Two `filter:false` badges in the existing pattern column
(`frontend/src/features/market/lib/tapeBadges.ts`): «متوقف» (red) and «نظارت» (amber),
each with a short title and "جزئیات درِ Inspector". They are not filter chips, so chip
counts and the seven filters are unchanged (`tape-badge-chip-parity` suite green).
`client_type_value`/`value_source` do **not** appear in the board UI.

Live board body (repo code, copy of `market.db`): 5669 rows; keys present only where a
record exists — `st_code/st_title/st_d/st_h` 223, `sup_flag/sup_reason_count/sup_reasons`
14, `stop_*` 25, `ctv_kind` 5669. Size: 4,909,223 bytes vs 4,735,382 before (≈+174 KB,
+3.7%); gzipped 612 KB.

## 7) Technical / Master — context, nothing else

- Sidebar tab 3 gets one line «از تابلو:» with chips `متوقف / نظارت / رویدادِ اخیر`,
  rendered only when data exists.
- The dock "داوری" tab gets one line naming the instrument state and stating that the
  verdict engine does not measure trading status.
- No score, no weight, no new signal, no gate change. `dev/tsetmc_p0_v1076.py` and the
  frontend spec `technical-board-context.spec.tsx` assert `stop_state`, `stop_reasons`,
  `sup_flag`, `sup_reason_count`, `ctv_kind`, `client_type_value` do not appear in
  `features/master/lib/strictGates.ts`, `features/technical/signals/technicalSignals.ts`,
  or `features/market/lib/tapeAlgorithms.ts`.
- Weekly→Daily pipeline, thresholds and the seven FTS filters untouched
  (`tape_filters_v1034` 216/0, `mstat_local_v975` 206/0, TA parity suites green).

## 8) API shape

No new endpoint. Extensions of existing canonical responses:
`/api/market` (+10 keys, presence-based), `/api/chart/{symbol}`,
`/api/chart/{symbol}` fallback, `/api/chart-db/{symbol}` (+`corporateEvents`).
`/api/mstat/mainwatch` was **not** extended with `value_source`: nothing in the UI reads
it and it would be another per-row key on 120 rows with no consumer; provenance reaches
the audit surface through the Inspector and the coverage report instead.

## 9) State semantics

`unavailable ≠ reject`, `empty ≠ error`, `no stop reason ≠ no instrument state` — encoded
as: NULL from SQL → key dropped by `_slim_records` → no chip/line; presence of
`supervision_state` row (not its `under_supervision` number, which is 0 even for
supervised symbols) decides «نظارت»; `instrument_state` is a change log, so the newest
row per instrument is used (`ROW_NUMBER` over `d_even DESC, last_h_even DESC`).
`corporateEvents` on an old DB (no P0 tables) is `[]` and the chart still works.

Bug caught and fixed in this round: the "JSON safety" pass in `api/market.py` turned
every NULL of the new keys into `0` on all 5669 rows — i.e. «موردی ثبت نشده» became
«وضعیتِ صفر». All ten keys are now in `_KEEP_NULL` (measured: body 5,595,239 → 4,909,223
bytes, and the sample rows show the keys simply absent).

## 10) Budget — measured, not raised

`CTV_BUDGET` is still 600 (asserted). New read-only tool:

```bash
python dev/tsetmc_native_coverage_report.py            # table
python dev/tsetmc_native_coverage_report.py --json     # machine-readable
```

Reading of the current DB:

| metric | value |
| --- | --- |
| session holding values | 20261004 (board session is 20261005 — the current session cannot be fetched) |
| target universe that session | 2243 symbols |
| native / mixed | 200 / 0 |
| reconstructed (no row) | 2043 |
| native coverage of target | 8.92 % |
| native coverage of traded board (3503) | 5.71 % |
| avg requests per symbol | 1.0 |
| next-run cache hit | 8.92 % |
| estimated requests/day: watchlist / funnel candidates / target | 0 / 600 / 600 (clipped at budget) |
| days to cover the traded board at 600/day | ≈5.8 |
| other P0 families per run | corporate 4, state+notices 3 (fixed, not symbol-scoped) |

The report tool is guarded (`part_report`, 10 new checks) and its first run corrected my
own arithmetic: I expected `reconstructed=3` for a 4-target fixture with 2 rows; the tool
said 2 and was right.

## 11) Left unresolved (documented status only, no work done)

| item | status |
| --- | --- |
| `corporateTypeCode` decode | no authoritative mapping found in any reviewed source; stored raw, never decoded, never used as a label. Chart type comes from the table, not the code. |
| orphan `stop_reasons` rows | **measured 0 today** (25/25 match `instruments.l_val18`). The 27 reported in `cf28e44` came from the pre-refresh DB; superseded, and the join is exact-match on the writer's own folding, so it can regress if webgw text changes. |
| per-symbol TSETMC messages | `GetMsgByFlow` has no `insCode`; `GetMsgByInsCode` costs ≈2 MB per symbol. Not implemented; the Inspector shows the three families it does have. |
| MarketWatch delta protocol | documented in `docs/TSETMC-DATA-GAP-MATRIX.md`; no change. |
| full native coverage | 8.92 % of the target session (§10). Raising it needs either more budget (refused) or multi-session backfill (not built). |
| `instrument_state` vs board gap | 228 instruments have state rows, 223 appear on today's board; 5 are delisted/suspended instruments with no board row. |
| External JEV textual review | not run in this round (see §13). |
| which build owns the last market_watch write on this machine | two backends share `market.db` here (8002 = not mine, 8003 = mine). `isin` refreshed, `flow` not. Needs one clean sync from a single build to confirm. |
| `۲۰۰-۱۲-۲۲` in `candle_contract.py:14` / `api/chart.py:80` | a mangled date that predates this round; the year cannot be confirmed from `price_history` (no `فولاد` row on 12-22 with H=L outside body: measured rows are 2024-12-22 O=6050 H=6060 L=5860 C=6000 and 2025-12-22 O=3874 H=3915 L=3781 C=3839), so it was left untouched rather than guessed. |
| guard copies of `market.db` | copying only `market.db` while a writer holds a 17 MB WAL yields `database disk image is malformed` (live `PRAGMA quick_check` = ok). One suite run failed exactly this way at 20:1x; re-run with all my servers closed. |

## 12) Tests

Backend (`dev/…`):
- `tsetmc_p0_v1076`: **127 passed / 0 failed** (97 → 127 this round; +10 report checks,
  +8 board/wiring checks, +3 tail-index checks, incl. `_KEEP_NULL` presence, named
  tape_history insert proven on an *upgraded-order* fixture, "no `_factors_from_events`
  reads corporate events", "no new endpoint").
- `mstat_local_v975` 206/0, `tape_filters_v1034` 216/0, `board_hist_cache_v1056` 24/0,
  `market_hot_state_v1077` 48/0. Two of those were broken by the new joins and fixed:
  their fixtures now build the P0 tables from `tsetmc_p0_schema` (single source) and the
  connection shims implement `rollback` so pandas surfaces the real SQL error.
- `dev/run_all_tests.py`: **85 suites OK, `ALL SUITES PASSED`** (see §13).

Frontend: `tsc -b` clean, `eslint` clean on every touched file, full suite
**1449 passed / 1 skipped (138 files)** — three new files:
`technical-corp-events.spec.ts` (8), `inspector-regulatory.spec.tsx` (7),
`technical-board-context.spec.tsx` (6).

## 13) Verification (what was actually run, and what was not)

Backend suite with every server I started closed: `python dev/run_all_tests.py` →
**85 suites OK, 0 failed, `ALL SUITES PASSED`**, including
`tsetmc p0 … rc=0 | 127/127`, `board history windows … 24 pass / 0 fail`,
`hot state … 48/48`, `mstat dashboard … 206/0`, `tape … 216/216`.
One earlier run failed only `board history windows` with
`sqlite3.DatabaseError: database disk image is malformed` — that was my own dev server
holding a 17 MB WAL while the guard copied `market.db`; live `PRAGMA quick_check` = `ok`,
and the same guard passed after I closed my server. Not a data problem.

Frontend: `tsc -b` clean · `eslint` clean on every touched file · `npm run build` clean ·
`npx vitest run` → **138 files, 1449 passed / 1 skipped** (21 of them new in this round).

Live UI (jev-browser Chromium against my own dev backend on 127.0.0.1:8003, built SPA
served by that backend, `sessionStorage` auth injected — no password typed):

| surface | evidence |
| --- | --- |
| board payload | `/api/market` 200, 5674 rows, `sup_flag` on 39, `stop_state` on 25, `ctv_kind` on all; `آريان` row carries `sup_flag/sup_reason_count/sup_reasons/ctv_kind` |
| tape badge | row «شپترو / پتروشيمي آبادان» renders «متوقف» with title `مشمول فرایند تعلیق — از ۱۴۰۵/۰۴/۰۲  عدم رعایت الزامات پذیرش (بند 1 ماده 38 دستورالعمل پذیرش)` |
| Symbol Inspector | before any selection: `data-regulatory-state="unavailable"` («اطلاعات در دسترس نیست»); after selecting آبادا through the app's own search palette: `state="stopped"`, head «متوقف — مشمول فرایند تعلیق / از ۱۴۰۵/۰۴/۰۲ / ۱ علتِ نظارت», details list علتِ توقف، علتِ نظارت و مبدأِ ارزش |
| Technical sidebar | `sidebar-board-context` = «از تابلو: متوقف نظارت», box 268×22 px, `clipped: []` |
| console | `consoleErrors: []` on both routes |
| chart payload | `/api/chart-db/فولاد` → `corporateEvents` 14 items (`shareChange` from 2011 on), `adjustEvents` 31 — the two arrays stay separate |

Not proven live:
- **canvas pixels of the chart markers** — the overlay is drawn on canvas and the chart
  instance is not reachable from the page; proof here is the payload, the shared mapping
  tests, and a clean console. A pixel check (per `canvas-chart-live-pixel-check`) is still
  open.
- **the second engine (FFC)** in a browser: mapping is shared and unit-tested, but no live
  FFC screenshot was taken.
- **pilot jev**: two `arbitrate` calls both died with
  `RuntimeError: TypeSafe Jev API Network Error: The read operation timed out`, so the
  prose arbitration of the «board row vs new per-symbol endpoint» fork did not happen.
- **a released EXE**: everything measured here is repo code on this machine.
- Environment note: a second, older backend kept rewriting the shared board cache/DB on
  this machine (127.0.0.1:8002, not started by me and left running). Two readings of the
  same screen differed because of it — the first tape click showed «موردی ثبت نشده» from a
  cache written by that build. Deterministic readings came only after the probe read the
  feed from my own server.


## 14) Files changed

| commit | files |
| --- | --- |
| `65ad58f` | `tsetmc_p0_schema.py` (new), `fts_terminal.spec`, `test_tsetmc.py`, `mstat_engine.py`, `api/market.py`, `frontend/src/shared/types/marketRow.ts`, `frontend/src/features/market/lib/tapeBadges.ts`, `dev/tsetmc_p0_v1076.py`, `dev/board_hist_cache_v1056.py`, `dev/market_hot_state_v1077.py` |
| `fadf1a0` | `api/chart.py`, `frontend/src/features/technical/api/useCandleFeed.ts`, `…/lib/corpEvents.ts` (new), `…/lib/ftsOverlays.ts`, `…/nahayatnegar/components/KLineChartWrapper.tsx`, `…/components/FtsEngineChart.tsx`, `…/routes/TechnicalPage.tsx`, `frontend/src/__tests__/technical-corp-events.spec.ts` (new), `dev/tsetmc_p0_v1076.py` |
| `21de16d` | `api/market.py`, `dev/tsetmc_p0_v1076.py`, `frontend/src/shared/types/marketRow.ts`, `frontend/src/features/market/components/RegulatoryState.tsx` (new), `frontend/src/widgets/SymbolInspector.tsx`, `frontend/src/__tests__/inspector-regulatory.spec.tsx` (new) |
| `e88a732` | `frontend/src/features/technical/components/SidebarActiveLevels.tsx`, `…/routes/TechnicalPage.tsx`, `…/lib/corpEvents.ts`, `frontend/src/shared/components/Badge.tsx`, `frontend/src/__tests__/technical-board-context.spec.tsx` (new) |
| `48ec3a2` | `dev/tsetmc_native_coverage_report.py` (new), `dev/tsetmc_p0_v1076.py`, `api/chart.py`, `mstat_engine.py`, `test_tsetmc.py` (three mangled Jalali dates) |
| `4730d5f` | `test_tsetmc.py` (`_MWI` + the after-hours UPDATE), `dev/tsetmc_p0_v1076.py` |

Architecture rule this round keeps: `TSETMC source → canonical layer (test_tsetmc) →
API/selectors (api/market.py, api/chart.py) → UI consumers (board badges, chart markers,
Inspector, sidebar)`. No UI file fetches TSETMC; no page computes the value again.
