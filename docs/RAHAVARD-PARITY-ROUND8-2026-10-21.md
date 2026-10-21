# Round 8 — Official Corporate Events Coverage, Rights-Issue Formula & Fixed-Income Fund Parity

Date: 2026-10-21
Branch: `mission/ra365-round8-event-coverage-2026-10-21`
Base/HEAD at start: `efa939299d11ed9463c6e0745d6fe6173013d612`
Status: **PARTIAL — improved and reproducible, not 100%**. Fund coverage is a
measured improvement; rights-issue `S`, pre-2024 stock DPS, and a handful of
funds remain `UNVERIFIED`/`BLOCKED`. No 100% claim is made.

## 1. Git, HEAD and real base

- Repository root: `C:/Users/Johnkallnaya/Desktop/Borsterminal`; source worktree
  `BorsTerminal-src`; mission worktree `.worktrees/ra365-round8`.
- Working branch: `mission/ra365-round8-event-coverage-2026-10-21`, created from
  `mission/ra365-100pct-parity-2026-10-20` at
  `efa939299d11ed9463c6e0745d6fe6173013d612`.
- `origin/main` at the start: `a14375c14cfb8fc616fb3312c685f8a5b0f79ab3`;
  the mission branch is 28 commits ahead, 0 behind. The Round 7 branch is not
  on GitHub (`ls-remote` shows only `main` plus unrelated sarkhati branches).
- `main`, tags and releases were not changed. No force push, reset, merge or
  release was performed. The mission branch is pushed only at the end (see §12).

## 2. Database protection (before/after)

| Item | Before | After |
|---|---|---|
| Operational DB `market.db` SHA-256 | `fff358a78be74e8d21961251a727116e102df84cea70f87b4dcb7da198667004` | `fff358a78be74e8d21961251a727116e102df84cea70f87b4dcb7da198667004` |
| Logical fingerprint (order-independent) | `cdb73c40a14f3fefbf6053bb65716e3cbc50f2af464b4dd2a1934ace2b73fcd4` | `cdb73c40a14f3fefbf6053bb65716e3cbc50f2af464b4dd2a1934ace2b73fcd4` |
| Isolated copy used for tests | `_scratch/ra365_round8/market_copy.db` SHA-256 `f2ad77e6dc8076c6e2ff8917524dc95deca47aeb83df1ee2fd2446909313621d` | unchanged |
| Fund-ingest copy | `_scratch/ra365_round8/market_fundtest2.db`, 244,285,440 bytes | 2,222 official fund rows; logical base fingerprint unchanged |

All tests ran through `dev/gate_db_guard.py` with `BORS_WORK_DIR`/`BORS_DB`
isolation and `BORS_NO_FETCH_LOOPS=1`. The operational DB was never opened for
writing. The copy path guard and logical fingerprint are described in
`dev/db_fingerprint.py`, `dev/test_db_isolation_v1.py` and
`dev/gate_db_guard.py`.

## 3. Reproducible full-universe baseline

The Round 7 “after” state was rebuilt from the fixed v4 corpus with the same
manifest, reference bars and product corpus. The reproduction is exact on every
headline metric:

| Metric | Round 7 after | Round 8 reproduction |
|---|---:|---:|
| Live Factor exact | 43.1729% (511,597/1,184,995) | 43.1729% (511,597/1,184,995) |
| Live Factor ±1% | 83.4797% (989,230/1,184,995) | 83.4797% (989,230/1,184,995) |
| Functional OHLC | 44.0722% (2,089,012/4,739,980) | 44.0722% (2,089,012/4,739,980) |
| Normalized Factor exact | 40.6642% | 40.6642% |
| Normalized Factor ±1% | 80.9775% | 80.9775% |
| REF_ONLY / PROD_ONLY | 654 / 137 | 654 / 137 |
| Step mismatch | 244 | 244 |
| Missing product / reference candles | 1,361 / 2,485 | 1,361 / 2,485 |
| Raw exact | 97.4991% | 97.4991% |

Fixed inputs and hashes (`_scratch/ra365_round8/v4_inputs_sha256.txt`):

- `ref_bars_v2.jsonl` `4b1ecb4c1effc4d5770c42521d96a2540a9c9f7b471d7cc710cd034712a8c17c`
- `product_live_final_v4.jsonl` `893b6d6aa1059d51a83bb7a44fd239d4c381695806562dd3dcdd3ed5d8ad9f27`
- `product_bars.jsonl` `1544228e701dea31933e133afcf9f6725964db0461f0e7b5b2c5422f1a61d5fc`
- manifest v2 `8d84ffd202dc1c2f9809269c416b43e8fa7a6134eab8b26c4a49da7d3b098590`

Metric definitions (unchanged from Round 7): live `factor = type7.close/type0.close`
per common date; exact ≤ 5e-4 relative, near ≤ 1e-2 relative; normalized divides
both series by their first common date; functional OHLC compares each OHLC field
after applying the product factor; steps are factor changes above 1e-7.

## 4. Official corporate events and importer (Axis 1)

### 4.1 What was added

`tools/fund_profit_sources.json` now lists **33 funds** (16 previously configured
plus 17 audited in this round). The existing deterministic ingester
`tools/fund_profits_ingest.py` was run only against the isolated copy
`market_fundtest2.db`.

| Result | Count |
|---|---:|
| Official fund rows resolved | 2,222 |
| Primary fund events (`RESOLVED_OFFICIAL_SOURCE`) | 1,255 |
| Variant-copy events (`..._COPIED_VARIANT`) | 967 |
| `NO_REFERENCE_PRICE` (audit only, not inserted) | 226 |
| `ZERO_OR_NEGATIVE_DISTRIBUTION` | 5 |
| Funds with current data | 8 |
| Funds with stale/partial data | 8 |
| Official portal with no distributions (اطلس) | 1 |
| Official portal empty (دانيك) | 1 |

Importer idempotence: a second run produced the same 2,222 rows and the same
SHA-256 of the ordered `(ins_code,d_even,symbol,profit_date,unit_profit,
reference_price,ratio,source,source_id)` multiset:
`85ed397a22fe507ddd126361ee83e1702b49a35b3ff206ead5c9d4f7b660abe0`.
The importer deletes and re-inserts per fund, so reruns do not duplicate rows.
Incomplete rows are kept in the audit CSV, never published as confirmed events.

Direct answers to the Axis 1 questions:

| Question | Answer |
|---|---:|
| Official events found | 2,222 rows / 32 funds (1,255 primary + 967 variant copies) |
| Ingested with sufficient data | 2,222 |
| Identified but not confirmed | 231 (226 `NO_REFERENCE_PRICE` + 5 `ZERO_OR_NEGATIVE_DISTRIBUTION`) |
| Still without a source | دانيك (0 rows), ارزش مسكن (2 rows), اطلس (no periodic distributions) |
| REF_ONLY steps actually resolved | 516 of 526 fund steps |
| New PROD_ONLY steps | 2 (امين شهر 2025-12-28, صايند 2020-10-07) |

Per-fund endpoints, fund ids and evidence strings are in
`tools/fund_profit_sources.json`; every inserted row carries
`source_id = <fund_id>:<profit_date>` and the source domain, so each step can be
traced back to the official portal row.

### 4.2 What the official rows changed

The production path `api.chart._fund_profit_events → _merge_official_fund_events →
_canonical_adjustment` was measured on the isolated copy against the reference.
Fund REF_ONLY steps fell from **526 to 10** (516 resolved). Remaining fund
REF_ONLY: اطلس 3, دانيك 3, ارزش مسكن 2, هامرز 2. The two new PROD_ONLY steps are
امين شهر 2025-12-28 and صايند 2020-10-07; both ratios are within ±1% of the
reference shape and represent a date-placement mismatch, not a new fabricated
event.

### 4.3 What remains for stocks

The 128 stock REF_ONLY steps are unchanged. 55 of the 138 total remaining
REF_ONLY steps are tiny reference changes ≤ 0.1% (e.g., 0.9991); 83 are material.
Largest groups: حبندر 10, ثعتما 6, ثنام 6, جهرم 5, تاتمس 3, ثنظام 3, غدام 3.
The TSETMC `price_adjust_events` feed only covers 2024-07 onward; pre-2024 DPS
and capital events are the gap. No official pre-2024 stock event was ingested in
this round, so these are `BLOCKED` on CODAL notices, not silently dropped.

## 5. Rights-issue / mixed capital-increase formula (Axis 2)

### 5.1 Reserve-only increases — VERIFIED

`price_ratio = previous_capital / new_capital` remains exact on the independent
marks samples:

| Symbol | Date | pv/nw | Reference |
|---|---|---:|---:|
| پخش | 2023-01-28 | 0.583333 | 0.583333 |
| پخش | 2024-03-17 | 0.558824 | 0.558824 |
| پخش | 2025-03-03 | 0.787037 | 0.787037 |
| سپاها | 2024-08-04 | 0.490000 | 0.490000 |
| سپاها | 2025-11-02 | 0.740741 | 0.740741 |
| وبشهر | 2021-11-29 | 0.550000 | 0.550000 |
| شسپا | 2021-02-27 | 0.631579 | 0.631579 |
| كلر | 2025-07-29 | 0.088942 | 0.088942 |

### 5.2 Contribution / mixed increases — UNVERIFIED

The structural form remains
`pv/nw + (1-pv/nw) * (cp/100) * (S/P)`, where `S` is the subscription price and
`P` the base/reference price. Solving for the implied `S/P` on independent
observed steps gives:

| Symbol | Step | pv/nw | cp% | Implied S/P |
|---|---|---:|---:|---:|
| حخزر | 2023-10-15 | 0.300000 | 100 | 0.02008 |
| حخزر | 2025-03-03 | 0.285714 | 100 | 0.14396 |
| پخش | 2023-04-11 | 0.631579 | 100 | 0.02886 |
| پخش | 2025-12-24 | 0.864000 | 100 | 0.12425 |
| وبشهر | 2024-02-10 | 0.600000 | 100 | 0.16380 |
| وبشهر | 2026-05-23 | 0.416667 | 40.602857 | 0.13334 |
| كلوند | 2025-08-26 | 0.719307 | 100 | 0.22063 |

The implied `S/P` is event-specific (2%–22%), not a constant. The formula fits
each event by construction (one unknown per event), so it is **not** independent
evidence for `S`. No official subscription price was found in the TSETMC
circulation or `timescale_marks`; the CODAL notice lookup was not completed.
The implied values were **not** stored as official `S`, and the formula was not
inserted into production logic. Status: `UNVERIFIED` / `BLOCKED` on the official
notice. The existing product behavior (base-price gap approximation) remains.

### 5.3 Tests required by the mission

Covered by `dev/test_dps_formula_v1.py`: reserve-only, capital formula, DPS
formula, missing reference, distinct events, same-day duplicate, share-change
attributed capital event, unattributable same-window duplicate. Contribution/
mixed with official `S` remains a test to add once `S` is sourced.

## 6. Fixed-income funds and ETFs (Axis 3)

### 6.1 Mechanism — VERIFIED

- Official fund manager portals publish monthly (or periodic) cash
  distributions with a Jalali profit date and rial-per-unit amount.
- The fund's raw price is reset toward the 10,000-rial base after distribution;
  the reference `type7` series is the adjusted history (`type0 × cumulative
  factor`). Charisma's own Kemand page states the reset-to-base behavior:
  “پس از پرداخت سود نقدی در پایان دوره، ارزش واحدهای صندوق به قیمت مبنا
  (۱۰۰۰۰ ریال) برمی‌گرده”.
- The fund adjustment is **not** a fixed 2.5% constant and not a single
  one-size-fits-all ETF coefficient. It is the cumulative product of official
  per-period distributions.
- The production engine recomputes the row ratio from `reference_price` and
  `unit_profit` as `(P − D)/P`; the stored `ratio` column is not trusted as the
  sole input. This matches the reference better than the stock DPS form
  `close_ex/(close_ex + D)` on the fund sample.

Validation across 33 official portals and 1,752 matched reference steps:
`(P_prev − D)/P_prev` is exact on 214, within 5e-4 on 1,624, median error
1.4e-5, max 0.0229. The alternative `P_ex/(P_ex+D)` is exact on only 35 and the
`ex_minus` form on 2.

### 6.2 Measured fund impact (production path, before → after)

| Symbol | Events applied | Common dates | Near before | Near after | Exact steps after |
|---|---:|---:|---:|---:|---:|
| كمند | 109 | 1,617 | 0.49% | **100%** | 69/82 |
| امين يكم | 100 | 1,617 | 1.18% | **93.32%** | 63/81 |
| هماي | 61 | 1,227 | 1.55% | **99.92%** | 57/61 |
| گنجينه | 46 | 1,592 | 41.77% | **100%** | 36/45 |
| نيلي | 43 | 848 | 0.94% | **100%** | 40/43 |
| كارين | 42 | 1,366 | 40.26% | **100%** | 38/42 |
| آكام | 40 | 781 | 0.64% | **100%** | 36/40 |
| صايند | 76 | 1,610 | 55.53% | **100%** | 24/35 |
| رشد | 21 | 1,042 | 61.71% | **100%** | 18/21 |
| اندوخته داريوش | 19 | 367 | 5.18% | **100%** | 15/19 |
| سيناد | 18 | 1,213 | 71.31% | **100%** | 17/18 |
| سام | 12 | 857 | 72.70% | **100%** | 10/12 |
| ثابت اكسيژن | 9 | 720 | 76.39% | **100%** | 9/9 |
| امين شهر | 7 | 581 | 5.34% | **100%** | 0/6 |
| ارزش مسكن | 2 | 883 | 11.10% | 11.10% (`PARTIAL`) | 0/4 |
| اطلس | 2 | 1,561 | 77.39% | 77.39% (`PARTIAL`) | 1/4 |
| دانيك | 2 | 672 | 5.95% | 5.95% (`BLOCKED`, empty portal) | 0/3 |
| هامرز | 54 | 1,097 | 27.99% | 27.99% (`PARTIAL`) | 48/56 |
| پالايش | 4 | 1,324 | 26.96% | 26.96% (`PARTIAL`, 3 annual rows) | 0/3 |

Status: 13 funds `VERIFIED` at ≥93% near coverage; 1 `PARTIAL` with a
date-placement issue (امين شهر); 5 `PARTIAL`/`BLOCKED` (ارزش مسكن, اطلس,
دانيك, هامرز, پالايش). No constant 2.5% or monthly coefficient was introduced.

## 7. Review of the seven Round 7 regressions

Round 7's ±1% loss was caused by correcting a DPS ratio that had been
accidentally compensating a larger remaining event error. The correction is
right; the exposed error is the old event.

| Symbol | Near before | Near after | Exact before → after | Remaining cause |
|---|---:|---:|---:|---|
| حخزر | 46.63% | 46.63% | 3.94 → 3.94% | DPS 6,300 (2023-06-21) still a base gap; mixed CC 2025-02-23 (`S/P≈0.144`) |
| پخش | 48.24% | 48.24% | 32.20 → 32.20% | DPS 1,200 (2023-05-21) still a base gap; mixed CC 2023-04-11 and 2025-12-24 |
| كلر | 49.16% | **100%** | 16.05 → 16.05% | 2026-07-15 date mapping fixed; reserve CC 2025-07-15 remains 0.46% off |
| سپاها | 55.77% | 55.77% | 24.61 → 24.61% | DPS 1,770 (2022-11-19) still a base gap |
| وبشهر | 6.40% | 6.40% | 6.40 → 6.40% | Mixed CC 2026-05-23 (`S/P≈0.133`); DPS 2026-07-13 now exact |
| شسپا | 62.74% | **100%** | 15.97 → 31.33% | 2026-07-25 DPS 2,000 date mapping fixed |
| كلوند | 94.30% | 94.30% | 15.02 → 15.02% | DPS 1,870 (2021-07-07) and 2,650 (2022-07-02); mixed CC 2025-08-26 (`S/P≈0.221`) |

For the five remaining DPS cases, the reference step is reproduced **exactly**
by `close_ex/(close_ex + D)` with the marks amount and the ex-date closing:

| Symbol | Step | Closing | DPS | Reference | Formula |
|---|---|---:|---:|---:|---:|
| حخزر | 2023-07-08 | 54,000 | 6,300 | 0.89552239 | 0.89552239 |
| سپاها | 2022-11-21 | 8,780 | 1,770 | 0.832227 | 0.83222749 |
| كلوند | 2021-07-07 | 20,350 | 1,870 | 0.915842 | 0.91584158 |
| پخش | 2023-05-23 | 26,000 | 1,200 | 0.955882 | 0.95588235 |
| وبشهر | 2026-07-13 | 4,640 | 480 | 0.906250 | 0.906250 |

These values are from Rahavard `timescale_marks`; they are reference-identified,
not yet official CODAL ingest. They are locked as fixtures in
`dev/test_dps_formula_v1.py` (`MARKS_DPS_CASES`) so a future change cannot
silently break them. Official CODAL notices are the remaining `BLOCKED` source.

The seven-symbol review also found a latent production bug: `_day_diff(...) or
999` treated a same-day difference (0) as unknown. It is fixed; a same-day
duplicate test was added. The old blanket “drop any base gap within 5 days of a
DPS” was also wrong for distinct capital events (بورس 2026-07-22: DPS 55 + reserve
CC 24T→32T). The merge now drops the gap only when its ratio agrees with the DPS
ratio, or keeps it when an official share change explains it.

## 8. Full-Universe before/after

Three states on the same universe, manifest, reference and product corpus:

| Metric | A: Round 7 after | B4: date-mapped (no funds) | C4: B4 + official fund events |
|---|---:|---:|---:|
| Live Factor exact | 43.1729% (511,597/1,184,995) | 50.6603% (600,322/1,184,995) | **50.8008%** (601,987/1,184,995) |
| Live Factor ±1% | 83.4797% (989,230/1,184,995) | 85.9472% (1,018,470/1,184,995) | **86.8274%** (1,028,900/1,184,995) |
| Functional OHLC | 44.0722% (2,089,012/4,739,980) | 51.5405% (2,443,010/4,739,980) | **51.6810%** (2,449,667/4,739,980) |
| Normalized Factor exact | 40.6642% | 40.8663% | **41.3119%** |
| Normalized Factor ±1% | 80.9775% | 81.1591% | **82.4241%** |
| Raw exact | 97.4991% | 97.4991% | 97.4991% |
| REF_ONLY | 654 | 654 | **138** |
| PROD_ONLY | 137 | 137 | 139 |
| Step pairs | 5,862 | 5,862 | 6,378 |
| Step mismatch | 244 | 217 | **217** |
| Missing product / reference candles | 1,361 / 2,485 | 1,361 / 2,485 | 1,361 / 2,485 |

Attribution:
- B4 is the **measurement-harness correction**: official `priceAdjust` ratios
  for non-trading `d_even` are now computed from the first candle on/after the
  event, matching production. It is not a new formula.
- C4 adds 2,231 applied fund/official events for 54 fund symbols (variants
  included) from the isolated copy. The 516 newly comparable fund steps account
  for the REF_ONLY drop and most of the step-pair increase.
- The denominator (1,184,995 live factor dates) is unchanged. The step-pair
  denominator intentionally rises from 5,862 to 6,378 because 516 REF_ONLY fund
  steps became comparable; the mismatch numerator stayed at 217, so the step
  mismatch rate fell. This is disclosed, not hidden.
- Missing candles and raw exact are unchanged: the intervention did not alter
  the universe, candle coverage, or raw OHLC.

### 8.1 Honest regressions

Exact coverage improved for 251 symbols, was unchanged for 2,318, and lost for
26; near coverage improved for 69, was unchanged for 2,513, and lost for 13.
The near losses are the exposed-compensation class; most exact metrics improved
at the same time:

| Symbol | Near A→C4 | Exact A→C4 |
|---|---:|---:|
| نوري | 100 → 3.21% | 3.21 → 3.21% |
| شپاكسا | 96.44 → 5.88% | 3.01 → 3.01% |
| نخريس | 100 → 10.87% | 10.87 → 10.87% |
| شپنا | 85.27 → 31.16% | 3.26 → **31.16%** |
| سفانو | 100 → 69.05% | 5.63 → **32.54%** |
| حكشتي | 69.33 → 42.54% | 0.97 → **27.62%** |
| كگل | 31.25 → 6.72% | 6.72 → 6.72% |
| سمازن | 100 → 81.43% | 7.19 → **21.98%** |
| فولاد | 100 → 84.28% | 3.53 → 3.53% |
| دكيمي | 100 → 85.41% | 20.14 → **34.39%** |
| وپويا | 100 → 88.17% | 22.80 → **35.48%** |
| ولشرق | 100 → 94.35% | 6.12 → **25.08%** |
| وصنا | 63.22 → 60.98% | 6.73 → **21.21%** |

Largest exact losses (26 symbols lost exact coverage in total, not hidden):
بورس 35.33→4.15% (near stays 100%; the mapped DPS base differs by ~0.24%),
غانيزان 28.88→18.63%, كرازي 6.39→3.91%, ومعادن 6.46→4.40%, تاصيكو 13.53→1.46%,
واميد 9.69→4.18%, وبشهر 6.40→4.58%. These symbols need their own event
investigations; the DPS correction was not reverted to buy back the old
accidental compensation.

## 9. Tests and final gate

Targeted suites:

- `dev/test_dps_formula_v1.py`: **30/30** (16 official DPS cases, 5 marks-DPS
  regression fixtures covering all seven symbols, 3 reserve CC cases,
  duplicate/ledger/share-change cases).
- `dev/test_fund_events_v1.py`: **10/10** (official rows read, `(P−D)/P`
  recomputation, same-date base gap replacement, typed split survival, factor
  chain, factor=1 on the last event date).
- `dev/test_fund_ingest_v1.py`: **7/7** (Persian digits, corrupt date/amount,
  duplicate legacy row dedupe, newest-instrument selection).
- Importer idempotence: same 2,222 rows and identical SHA on a second run.
- Full gate: see §9.1 (final result after the last change).

### 9.1 Full gate

`python dev/run_all_tests.py` was run through `dev/gate_db_guard.py` on the
isolated workdir. Final result: **139 suite counted, 36 silent (exit-code only),
0 skipped (fixture missing), 0 failed — ALL SUITES PASSED**. The three new
suites are in the 36 silent list because they print custom counts; their
standalone results are 30/30 (DPS), 10/10 (fund events) and 7/7 (fund importer).
Protected DB logical fingerprint after the gate:
`cdb73c40a14f3fefbf6053bb65716e3cbc50f2af464b4dd2a1934ace2b73fcd4`
(unchanged; `PROTECTED_DB_UNCHANGED`).

## 10. Resolved and unresolved rows

### Resolved this round
- 516 fund REF_ONLY steps (526 → 10) via 2,222 official portal rows.
- 27 step mismatches (244 → 217) via the production date-mapping correction.
- Seven-symbol: شسپا and كلر restored to 100% near.
- Latent same-day `_day_diff` bug and the over-broad 5-day base-gap drop.

### Unresolved / blocked
- 128 stock REF_ONLY steps, including 55 tiny ≤0.1%; pre-2024 DPS/CC needs
  CODAL notices.
- 10 fund REF_ONLY: اطلس 3, دانيك 3, ارزش مسكن 2, هامرز 2.
- 2 new PROD_ONLY fund dates: امين شهر 2025-12-28, صايند 2020-10-07.
- Rights-issue `S`: no official subscription price; formula `UNVERIFIED`.
- 13 near-loss symbols and 7 exact-loss symbols listed in §8.1.
- 5 fund groups `PARTIAL`/`BLOCKED`: ارزش مسكن, اطلس, دانيك, هامرز, پالايش.

## 11. UNVERIFIED and BLOCKED

| Item | Status | Reason / next action |
|---|---|---|
| Rights-issue subscription price `S` | `UNVERIFIED` / `BLOCKED` | Official CODAL notice with the subscription price and effective date not obtained. Do not use the implied `S/P`. |
| Pre-2024 stock DPS (حخزر 2023, سپاها 2022, كلوند 2021/2022, پخش 2023) | `UNVERIFIED` | Marks identify the exact DPS and the formula fits, but the values are reference-identified, not official notices. |
| دانيك | `BLOCKED` | Official portal returns 0 distribution rows. |
| ارزش مسكن | `PARTIAL` | Only 2 official rows; reference still 11% near. |
| اطلس | `PARTIAL` | Official portal reports no periodic distributions; the remaining steps are a different mechanism. |
| هامرز | `PARTIAL` | 54 official rows, but a constant offset leaves near at 28%; the anchor/coverage needs investigation. |
| پالايش | `PARTIAL` | 3 annual rows; near 27%; annual schedule may not match the reference step shape. |
| Live chart-mode combinations | `BLOCKED` | Local app login required; no credentials requested. |

## 12. Commits, push and main

- Commit 1 (code/tests/sources): `22850f82532437a2e6b781d17fc62ae2d3e16b9f` — official fund sources, share-aware DPS/base merge, same-day fix, new tests, rule-map citations.
- Commit 2 (docs): `42e047308cf4f471d44c00b5570df3312ce9176e` — this report, the chart matrix and the prototype.
- Push: only the mission branch `mission/ra365-round8-event-coverage-2026-10-21`.
- `main`, tags and releases: unchanged. No merge, no force push.

---

## Appendix A — Chart modes and price adjustment (mandatory audit)

Full matrix: `docs/CHART-MODES-FEATURE-MATRIX-2026-10-21.md`.
Prototype: `docs/prototypes/chart-mode-controls-2026-10-21.html`
(rendered locally; no main code changed).

Summary:
- The main chart has exactly two price bases, `none` (raw) and `combined`
  (functional), and three scales, `normal`, `logarithm`, `percentage`. Basis and
  scale are independent; log is not a price basis.
- The second engine (FFC) deliberately has no basis dropdown and always renders
  `combined`; it does support the shared scale. The market-status page embeds
  the same main chart component.
- The compare chart is normalized and exposes only `pct`/`log`; the mini charts
  and the strategy canvas have no basis/scale controls (scope limitation, not a
  removed feature).
- Standard indicators follow the selected price series; FTS layers stay in raw
  server space and are mapped to the display. Drawings are stored per symbol
  without a basis key and are restored as-is, so a basis switch can move them.
  Basis selection is visible in the toolbar but not persisted outside a chart
  template; scale is persisted.
- Live combination testing (all four basis×scale pairs, drawing/indicator
  behavior, reload persistence) is **BLOCKED** on local app login. The test plan
  is in the matrix §7. No control was removed or regenerated in this round.
- Scope note: the `api/chart.py` changes in this round are parity/data-chain
  fixes required by the Round 8 spec (corporate events, DPS date mapping,
  fund merge). No chart engine, chart UI component, scale control or drawing
  behavior was changed by the chart-mode audit; that audit is research and a
  static prototype only, pending the owner's design direction.

---

## Appendix B — Artefacts and hashes

All paths are under `C:/Users/Johnkallnaya/Desktop/Borsterminal/_scratch/ra365_round8/`
unless noted. These files are outside Git (scratch corpus), but their hashes and
generating scripts are recorded here so the run can be reproduced.

| Artefact | SHA-256 |
|---|---|
| `fund_ingest2_audit.csv` | `aff0fb6fb8b24e5e49eb846b9f27c7628c79d0b2e09e6dbd62dab23f1c377292` |
| `fund_formula_compare2.csv` | `a822459076225b3e92cbdc1bbf0e71f2eaa26d913b03bb9d3c71aff48e7ca978` |
| `fund_engine_measure.csv` | `6d192f27989c069a4cb79ccf6d6b7beacef0e1082f4bcf55b0a464509b7df2e8` |
| `marks_explain_7sym.csv` | `fbdaf83b287524983a0c11e3d01b8e335de89e3bcaa71dcc3baf978ca381af5c` |
| `after_C4_funds/parity_summary.json` | `d4ebf8db041dc92f963f248a4d36cd8b8768806e124ae321c3ffc88947a98298` |
| `after_C4_funds/parity_steps.csv` | `c363b97755d3c04a25d868dd9e3807a0c9fcd04f19a268b582193a2d282dba33` |
| `market_fundtest2.db` (isolated, 2,222 fund rows) | `e13c061fe3c27e2d737c72160d4c12f91719e552db8d1deb280e32350eb6e11a` |
| `market_copy.db` (pristine isolated copy) | `f2ad77e6dc8076c6e2ff8917524dc95deca47aeb83df1ee2fd2446909313621d` |

Generating scripts (scratch, not committed): `r8_baseline_runner.py`,
`r8_run_parity_v5.py`, `r8_fund_formula.py`, `r8_fund_engine_measure.py`,
`r8_marks_explain.py`, `r8_inventory.py`, `r8_funds.py`, `r8_fund_product.py`.
The committed production artifacts are `api/chart.py`,
`tools/fund_profit_sources.json`, `dev/test_dps_formula_v1.py`,
`dev/test_fund_events_v1.py`, and `dev/run_all_tests.py`.
