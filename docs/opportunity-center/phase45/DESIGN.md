# Phase 4.5 — Technical Data Integrity, Rahavard Parity & Performance

**Status:** APPROVED by the owner on 2026-11-09 (chat).
**Base commit:** `da513ae939c26ed525465b6f85d305057da7ecf9`
**Branch:** `mission/phase45-technical-data-integrity-2026-11-09`
**Worktree:** `C:/Users/PCMOD/Desktop/BorsTerminal-phase45-2026-11-09`

This document is the committed design of record for the Phase 4.5 mission. The
mission itself (the owner's 12-section document) is the requirements authority;
this file records the verified environment, the approved approaches, the stage
plan, and the evidence contract.

## 1. Purpose and boundaries

Bring the BorsTerminal candle/adjustment/technical data path to a verified,
reproducible state before Phase 5:

1. 30-symbol data-integrity pilot against Rahavard (raw and adjusted, D/W/M).
2. Root-cause and fix of the Phase 4 open item `chartdb` / adjustment ledger.
3. Validation of existing technical calculations where the formula, settings,
   timeframe and price basis are identical.
4. Data-service architecture integrity.
5. Performance baseline and output-preserving optimisation.
6. Real `go test -race ./cmd/borsd` in GitHub Actions.

Out of scope: new Phase 5 indicators, FTS rule changes, `/fts-screen` changes,
Approved/Stable paths, main/merge/tag/release, operational DB rebuild or
replacement, any secret in the repository.

## 2. Verified preconditions (2026-11-09)

| Item | Status | Evidence |
|---|---|---|
| P0.9 base | PASS | branch `mission/phase4-p0-acceptance-2026-11-09` at `da513ae9`; clean tree |
| Other worktrees | untouched | 40+ worktrees listed; no writes |
| GitHub Actions | PASS | `guards.yml` on `ubuntu-latest`, Go 1.27.3; Actions enabled |
| `gh` CLI | PASS | account `johnwarchief`, scopes include `repo` and `workflow` |
| Operational DB | PASS (read-only copy) | `v1080_verify/app/market.db`, 307,171,328 bytes; 467,028 candles; 6,503 symbols; 0 duplicate symbol-dates; 0 null OHLC; 2,692 zero/null-volume rows |
| Bors coverage | measured | 2024-08-24 → 2026-11-04; 527 sessions maximum |
| `live40` correction pack | PASS | `data/ra365_corrections/ra365-live40-v1`; 828 assets; as_of 2026-11-04; 7,006 replace steps; asset mapping present |
| DB ∩ pack | 585 of 828 | 243 DB-only and 243 pack-only symbols (coverage-gap populations) |
| R32 raw reference pack | PARTIAL | 6 symbols; 19,802 bars D/W/M; 1992-11-22 → 2026-10-25 |
| Rahavard capture driver | PARTIAL | `tools/ra365/r32-reference` exists in the R32 worktree, not on the P0 base; port with provenance |
| Market | closed | after 12:30 Tehran; §5a cannot be measured without a session window |
| B3 baseline | FAIL | `49 passed / 1 failed`; six `s1/chartdb_*` goldens are Go output, the oracle is Python |
| Secrets | PASS | the capture driver fetches the token inside the page; it is never printed or stored |

## 3. Findings that shape the plan

1. **Coverage, not price, is the first difference.** BorsTerminal starts at
   2024-08-24; Rahavard monthly history reaches 1992. Dates outside the Bors
   window are recorded as coverage differences, never as price mismatches.
2. **A real coverage gap exists.** `خودرو` has 92 candles in the operational DB
   but 754 D bars from 2023 in the R32 reference. This is a pilot case, not a
   price comparison case.
3. **Identity needs normalisation.** `adjust_events` contains both `کگل`/`كگل`
   and `دعبيد`/`دعبید`; `d_even` is an integer while `price_history.date` is
   ISO. Selection and comparison use `ins_code` + `symbol_identity.py`, never
   a raw symbol string or a simple `paper_type` filter.
4. **B3 is a contract divergence.** The six chartdb goldens were produced by
   Go's `-update`; the Python oracle is `api/chart.py::get_chart_db`. The fix
   is the canonical Go port plus goldens generated from Python with provenance;
   no Go-regenerated chartdb golden is accepted.
5. **The `adjustment` axis was an explicit owner decision.** The UI sends
   `?adjustment=3` by default and `ChartSchema` treats the response key as
   optional. The owner approved keeping the capability while removing the
   numeric canonical key (see §4).

## 4. Approved approaches and decisions

| Area | Approved approach | Rejected alternatives |
|---|---|---|
| Adjustment engine | **A1:** port the canonical Python chain (effective dates → chain → coverage → functional state → ledger sharpening → correction pack → candle contract) to Go, driven by Python oracle goldens | A2 precomputed Python artifacts served by Go; A3 field-level patch |
| Rahavard reference | **B1:** CDP capture driver in the owner's authenticated browser; **B2:** CSV import fallback | B3 existing R32 pack only (6 symbols, stale) |
| Evidence | **C1:** aggregate summaries + scripts + 30-symbol CSV committed; raw Rahavard bars, full mismatch CSVs and screenshots local-only under `_audit/phase45/` | C2 committing raw reference series |
| Live | **D1:** §5a NOT_MEASURED in this run; §5b post-session final after a fresh lab sync and capture; optional 10-minute read-only session probe | Using historical data as live data |
| `adjustment` (owner ruling) | Keep `?adjustment=0..3` as an explicit Go capability; **omit the numeric `adjustment` key from the canonical body** so it matches Python; mode 3 is the parity mode; modes 1/2 remain typed extensions with their own tests; no UI capability is removed | Full removal + UI change; keeping the key with a parity exception |

The `adjustment` ruling preserves the UI's raw/adjusted capability and the
Python contract at the same time. `useChart.ts`/`forecastApi.ts` keep sending
the parameter; no frontend change is required unless a later audit proves one.

## 5. Execution stages

| Stage | Work | Output | Gate |
|---|---|---|---|
| S0 | worktree + design + `.gitignore` | this file | clean tree, base SHA |
| S1 | `go-race` CI job | `CI-RACE.md` + run URL | race job actually runs |
| S2 | lab snapshot + 30-symbol selection | `SYMBOLS-30.csv` | 30 symbols meet §2; source hash unchanged |
| S3 | Rahavard capture (D/W/M, type0/type7) | local export + access table | no secret stored; per-symbol status |
| S4 | raw D/W/M comparison | `RAW-PARITY.md` + local mismatch CSVs | full coverage + common range + causes |
| S5 | canonical adjustment port + Python goldens | Go code + tests | B3 `37/37`; raw candles unchanged |
| S6 | adjusted/reference parity + corporate events | `ADJUSTED-PARITY.md` | factor/event parity; correction pack marked |
| S7 | technical matrix | `TECHNICAL-PARITY.md` | identical formula/settings/TF/basis only; FTS independent |
| S8 | data-service architecture audit | `ARCHITECTURE.md` + targeted fixes | verified violations only; no parallel engine |
| S9 | performance B0 → B1 → B2 | `PERF.md` | output hashes unchanged; coverage unchanged |
| S10 | live §5a/§5b | `LIVE.md` | closed market ⇒ NOT_MEASURED |
| S11 | final report, commit, push | `FINAL-REPORT.md` | 10 items; SHA; CI link; no merge/release; wait for Phase 5 |

## 6. 30-symbol selection

The selector is `tools/phase45/select_symbols.py`, derived from the existing
`tools/phase5f_select_symbols.py` (which already records `ins_code`, the
event/control/hard-class criteria and the `d_even` normalisation bug). It reads
the lab copy read-only and the `live40` pack for the asset mapping. The output
is `docs/opportunity-center/phase45/SYMBOLS-30.csv`.

| Stratum | Quota | Criterion |
|---|---|---|
| High liquidity | 6 | 90-day average traded value |
| Mid liquidity | 5 | same, median band |
| Low liquidity | 4 | same, lower tail with >=120 sessions |
| Corporate events | 5 | `adjust_events` / `share_change_events` / correction pack; multi-event and combined |
| Halt/reopen | 3 | `tsetmc_messages` halt notices + date gap + `instrument_state` |
| Long history | 3 | >=450 sessions |
| Short / coverage gap | 2 | 120–200 sessions or `خودرو`-class (short DB, long reference) |
| Incomplete/special | 2 | repeated zero volume, alias/Arabic codepoint, fund/right |

Overlaps are resolved deterministically; each symbol is assigned to its
strongest stratum and the reason is recorded. If a stratum is short of
candidates, the gap is recorded rather than filled with a fabricated row.

CSV columns: `symbol`, `ins_code`, `isin`, `asset_id`, `stratum`, `reason`,
`first_date`, `last_date`, `candles`, `zero_volume`, `max_gap`,
`adjust_events`, `share_events`, `correction_pack`, `halt_state`,
`rahavard_access`, `raw_status`, `adjusted_status`.

## 7. Comparison methods

### 7.1 Raw candles (D/W/M)

- Bors `price_history` vs Rahavard `type0`; price basis resolved by the frozen
  `price_basis`/`pricebasis` contract before any value comparison.
- Report full coverage of each source **and** the common range; missing history
  is a coverage difference, not a price difference.
- Check missing/duplicate dates and order. Bors has 0 duplicate symbol-dates;
  Rahavard monthly repeats are collapsed by the importer and reported as
  `duplicate_rows_dropped` vs `conflicting_duplicates`.
- Record every difference locally with date, Bors value, Rahavard value,
  absolute/percent difference and probable cause. Causes: coverage, raw value,
  volume unit/basis, duplicate, corporate-action discontinuity, rounding,
  source revision, unclassified. The committed report carries aggregate counts
  and the mismatch taxonomy; the full table stays local (licence).

### 7.2 Adjusted candles and corporate events

Two independent questions:

1. **Engine parity:** Python and Go `chartdb` on the same lab DB for the 30
   symbols. Field-by-field: `adjustCapability` (availability, chain, coverage,
   corrections, functional status/blockers/reason, ledger sharpened/ambiguous),
   `candles[].date/src/symbol`, `adjustEvents[].source`, `adjustRejected`,
   `effective event dates`, `adjustSource`, `factors`. `indexed_available` is
   removed. The canonical body omits the `adjustment` key per §4.
2. **Reference parity:** Bors canonical factors/events vs the `live40` pack
   (input, marked as dependent) and vs fresh `type7` captures / the six R32
   anchors (independent where available). W/M uses a three-way comparison:
   Bors aggregation, Rahavard D→W/M aggregation, and Rahavard native W/M. The
   `ra365-r32d` calendar pack is the week/month authority.

No new tolerance is invented. The existing R32 factor convention
(`reference_adjusted / product_raw`) and its 0.1% factor tolerance are used and
reported alongside exact-match counts. Every acceptance claim names its
evidence.

### 7.3 Technical calculations

Inventory only the existing standard indicators (MA/EMA, RSI, MACD, Bollinger,
ATR, SuperTrend, volume, returns). Compare only where formula, settings,
timeframe and basis are identical. If Rahavard's own indicator output is not
extractable, apply the same formula to Rahavard bars and label the method.
FTS, the funnel and the lexicographic ranking stay independent and unchanged.
No new Phase 5 indicator is developed.

### 7.4 Live validation

- **§5a intraday:** closed market ⇒ NOT_MEASURED in this run. A committed,
  time-stamped probe (`tools/phase45/live_probe.py`) samples Bors and Rahavard
  at one instant, records receive/observe times, OHLCV deltas, latency,
  provisional/final state. It may be run in a short read-only session window
  only if the owner authorises it; historical data is never relabelled as live.
- **§5b post-session final:** after a lab-copy sync and a fresh capture,
  compare the final 2026-11-09 candle. If sync or capture fails, NOT_MEASURED.

### 7.5 Performance (only after correctness)

- Corpus: the 30 symbols and D/W/M on the frozen lab snapshot.
- B0: base `da513ae9`; B1: after the correctness fixes; B2: after each
  optimisation.
- Metrics: wall time, query count, bytes read/transferred, RSS/CPU, API
  p50/p95/p99, response size. `go test -bench -benchmem` + cpu/mem profiles;
  `EXPLAIN QUERY PLAN` and index lists; a benchmark-only query counter.
- No optimisation may change the output hash, the golden tests or the history
  coverage. Faster with divergent output is a failure.

### 7.6 Hard gates

- `dev/test_chart_fixture_b3.py` = `37/37` without Go-regenerated chartdb
  goldens.
- `go test -race ./cmd/borsd` green in CI, plus generation-runtime race tests.
- Raw OHLCV preserved; fixed input reproduces the same output.
- FTS rules, `/fts-screen`, lexicographic ranking, `approval_enabled=false`,
  and existing capabilities unchanged.

## 8. CI race detector

Add to `.github/workflows/guards.yml`:

```yaml
  go-race:
    name: go race detector (cmd/borsd + generation runtime)
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend-go
    env:
      CGO_ENABLED: "1"
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version: '1.27.3'
          check-latest: true
          cache-dependency-path: backend-go/go.sum
      - name: GCC (race detector requires cgo)
        run: gcc --version
      - name: Race Detector (borsd)
        run: go test -race -count=1 ./cmd/borsd
      - name: Race Detector (generation runtime)
        run: go test -race -count=1 ./internal/generation/... ./internal/snapshot/... ./internal/pointerfile/...
```

A push to the mission branch triggers the workflow. The run URL, job
conclusion and relevant log excerpt are recorded in `CI-RACE.md`. A green
ordinary test suite is not a substitute. If the job fails, the real cause is
fixed; nothing is skipped.

## 9. Evidence, licensing and secrets

Committed:

- this design;
- `SYMBOLS-30.csv`;
- aggregate coverage/raw/adjusted/technical reports;
- `PERF.md`, `CI-RACE.md`, `FINAL-REPORT.md`;
- the selector, comparison, capture-wrapper and benchmark scripts under
  `tools/phase45/`;
- the ported capture driver with a `PROVENANCE.md` (source commit, file
  hashes, licence note).

Local-only (`_audit/phase45/`, ignored):

- the Rahavard capture exports;
- full per-date mismatch CSVs;
- chart screenshots.

The R32 pack README states that reference OHLC is the owner's subscription and
must never be published. The committed reports carry paths and aggregate
counts. No cookie, token, account id or password is ever printed, stored,
committed or sent anywhere. The capture driver fetches the token inside the
page and returns only bar JSON. The owner performs the login; Computer Use is
used only for UI observation/screenshots, never for authentication or
terminal automation.

## 10. Risks and expected statuses

| Risk | Effect | Mitigation |
|---|---|---|
| Rahavard session expired | §3/§4 raw/§5 insufficient | owner logs in once in the CDP window; otherwise explicit NOT_MEASURED/INSUFFICIENT_DATA |
| Fresh sync blocked/WAF | §5b | 2026-11-04 baseline remains; status explicit |
| Linux race failure | S1 red | early run; fix the real cause |
| `live40` is derived from Rahavard | circular adjusted evidence | mark dependent symbols; use R32 anchors + fresh capture as independent evidence |
| Alias/Arabic codepoints | wrong selection/diff | `ins_code`, `symbol_identity.py`, normalisation |
| Stale DB shown as live | wrong UI claim | lab snapshot + `liveInjected`/`as_of`; operational DB untouched |

Status vocabulary at every level: `PASS`, `FAIL`, `NOT_MEASURED`,
`INSUFFICIENT_DATA`, `DEFERRED`. Every PASS names its evidence.

## 11. Constraints and compliance

- `approval_enabled=false`; no Approved/Stable path.
- FTS remains independent and canonical; `/fts-screen` unchanged; lexicographic
  ranking preserved; no Composite Score/Weight.
- No new Phase 5 indicator.
- UI changes only if necessary to show/test data state; existing capabilities
  and animations are not removed; visual claims wait for the owner's verdict.
- No destructive reset, no operational DB rebuild/replacement, no main change,
  no merge, no tag, no release.
- Commits only on the mission branch; push only that branch.

## 12. Definition of done

The final report states, with evidence and statuses:

1. data integrity for each of the 30 symbols;
2. raw-candle parity;
3. adjusted-candle parity;
4. adjustment engine and corporate events;
5. D/W/M status;
6. existing technical calculations;
7. live result;
8. before/after speed and resources;
9. the real `go test -race` CI result;
10. open items and their exact causes.

Then: commit + push on the mission branch, exact SHA, CI run link, worktree and
main status. No merge/release. Phase 5 starts only after the owner's approval.

## 13. References

- owner mission attachment (Phase 4.5, 2026-11-09);
- `docs/opportunity-center/PHASE4-OPEN-chartdb-adjustment.md`;
- `data/ra365_corrections/ra365-live40-v1/manifest.json`;
- `data/ra365_calendar/ra365-r32d/`;
- `tools/ra365/r32-reference/README.md` (R32 worktree; driver provenance);
- `tools/phase5f_select_symbols.py`;
- `tools/parity/gen_chart_golden.py`;
- `dev/test_chart_fixture_b3.py`;
- `.github/workflows/guards.yml`.
