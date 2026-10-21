# Round 11 — Visual Verification + Production Parity Convergence

Date: 2026-10-21
Branch: `mission/ra365-round11-visual-parity-convergence-2026-10-21`
Base: `8513cd24880aa7403a9f645db5c37eec9f83b181` (Round 10)
Status: **NUMERICAL: IMPROVED (small) · VISUAL: BLOCKED_NO_AUTHORIZED_SESSION**
No 100% claim.

## 1. Executive summary

The Round 10 production baseline was reproduced exactly: Factor exact
48.3147%, ±1% 81.5694%, functional 48.7637%, normalized 41.2898/82.0320,
REF_ONLY 155, PROD_ONLY 158, mismatch 262 on 2,595 assets and 1,187,945
factor dates.

The visual path could not be verified: the connector tab opened the Rahavard
آکو page but showed the login modal, so there is no authorized session.  No
credential, cookie or token was requested or stored; the six requested symbols
are recorded as `BLOCKED_NO_AUTHORIZED_SESSION` in
`docs/audit/ra365-round11-visual-comparison.csv`.  No chart/tooltip evidence is
claimed.

The numerical path produced one small, safe improvement: the official
share-change table contains reverse rows (ratio > 1) and repeated identical
ratios months later (وبشهر 0.41666667 on 2026-04-12 and 2026-07-12 with a
reverse 2.4 between).  Filtering those rows removed a false capital
attribution.  Full-universe result:

| Metric | Before | After | Δ |
|---|---:|---:|---:|
| Factor exact | 48.3147% | 48.3147% | 0 |
| Factor ±1% | 81.5694% | **81.5943%** | +0.0249pp (+296 dates) |
| Functional OHLC | 48.7637% | 48.7637% | 0 |
| Normalized exact / ±1% | 41.2898 / 82.0320 | 41.2898 / 82.0320 | 0 |
| REF_ONLY / PROD_ONLY | 155 / 158 | **154 / 157** | −1 / −1 |
| Step pairs | 6,361 | 6,362 | +1 |
| Step mismatch | 262 | 263 | +1 |
| Missing product / reference | 1,845 / 2,170 | 1,845 / 2,170 | 0 |

Only كگل changed: near 451→747 (+296), exact unchanged.  No symbol lost exact
or near in this iteration.  The +1 step mismatch is the one step whose
classification changed with the filtered share rows; it is recorded rather
than hidden.

## 2. Git, branch and database

- Branch `mission/ra365-round11-visual-parity-convergence-2026-10-21` from
  Round 10 `8513cd24`; Round 10 and `main` unchanged.
- Operational DB stayed `fff358a78be74e8d21961251a727116e102df84cea70f87b4dcb7da198667004`.
- All experiments use the isolated `market_r9_base.db`; no operational
  backfill or migration.  Gate temp workdir is on D:
  (`D:\BorsTerminal-tmp\ra365_round11\gate_work6`).

## 3. Path A — Rahavard visual verification

- Direct new tab to `https://rahavard365.com/asset/48315/chart` (آکو) loaded
  the page title but presented the login modal.  No authorized session.
- Per the mission, the owner was not asked to log in and no credential was
  requested.  Status: `BLOCKED_NO_AUTHORIZED_SESSION`.
- The visual CSV has six rows (آکو, حخزر, شپاكسا, وبشهر, سپاها, ومعادن) with
  no compared points, no screenshot IDs and the exact cause.  The 5/5 mock
  chart test from Round 9 is **not** presented as visual verification.
- The four basis×scale combinations remain covered only at the isolated test
  layer; live pixel/drawing behavior is `LIVE_UI_UNVERIFIED`.

## 4. Path B — numerical iterations

1. **Baseline reproduction** — exact (see §1).
2. **Worsened-row analysis** — the 15 Round 10 worsened rows and 11 near-loss
   symbols were traced.  Causes split into:
   - share-table noise: reverse rows and a repeated identical ratio
     (وبشهر) feeding a false capital attribution;
   - mixed capital increases without an official subscription price
     (وبشهر/سپاها/ومعادن): the reference needs the `S` component; the base
     gap is an approximation;
   - DPS compensation: a small (≈0.36%) DPS ratio change moved a previously
     compensated series outside ±1% (شپاكسا), while exact may improve;
   - small (<0.5%) DPS-formula differences where the old PA ratio is only
     coincidentally closer (the 15 DPS-only rows).
3. **Share-noise filter** — `_filter_share_changes` drops ratio > 1 and
   dedupes the same ratio within 180 days (keep earliest).  Tests cover
   وبشهر’s triple and a distinct same-ratio event 19 months later (51/51 DPS
   tests).  Full-universe result in §1.
4. **Share-only 284** — 30 rows match the reference step within 1e-4, but
   reserve-only vs contribution is not proven; CODAL is rate-limited.  No
   row was ingested; status `BLOCKED_TYPE_EVIDENCE`.
5. **DPS-only** — the remaining rows were left unchanged; a threshold guard
   would be reference-fitting and was not shipped.  The 15 worsened rows stay
   in the delta with their causes.

## 5. Round 10 regressions (carried, not hidden)

The 11 near-loss symbols remain: شپاكسا, شپنا, پخش, سفانو, سپاها, وبشهر,
سمازن, ومعادن, كلوند, ولشرق, وصنا.  The four worst:

| Symbol | Exact (Round 10 base → now) | Near (base → now) | Likely cause |
|---|---:|---:|---|
| شپاكسا | 44 → 44 | 86 → 86 | DPS compensation; exact unchanged |
| وبشهر | 68 → 68 | 68 → 68 | mixed CC without official S/P |
| سپاها | 375 → 375 | 850 → 850 | mixed CC / DPS type |
| ومعادن | 64 → 64 | 64 → 64 | combined CC + DPS |

The share filter did not repair these; it only removed the false attribution
for كگل.  A real fix for وبشهر/سپاها/ومعادن needs the official contribution
component (`S`), not a metric threshold.

## 6. Tests and gate

- `dev/test_dps_formula_v1.py`: **51/51** (adds share-noise reverse/duplicate
  tests).
- `dev/test_official_ledger_dedupe_v1.py`: **7/7**.
- `dev/test_fund_events_v1.py`: **10/10**; importer **7/7**; fund/backfill
  **20/20**; frontend matrix **5/5**.
- Full gate: see §7 (running on D:).

## 7. Full gate

First full run: **139 suite counted, 36 silent, 0 skipped, 1 failed**.  The
only failure was `shared mstat snapshot cache` with “phases raised
OperationalError: unable to open database file”; the same suite passes 10/10
standalone and 10/10 with the gate’s D-temp environment, so it was a transient
file-lock/path failure, not a code regression.

Clean full rerun (fresh workdir on D:/BorsTerminal-tmp/ra365_round11/gate_work6):
**139 suite counted, 36 silent (exit-code only), 0 skipped (fixture missing),
0 failed — ALL SUITES PASSED**.  Protected DB logical fingerprint after the
rerun: `cdb73c40a14f3fefbf6053bb65716e3cbc50f2af464b4dd2a1934ace2b73fcd4`
(unchanged; `PROTECTED_DB_UNCHANGED`).  The new DPS/ledger/fund suites are in
the 36 silent list; standalone counts are 51/51, 7/7, 10/10, 7/7 and 20/20.

## 8. Open clusters and next experiments

1. **Mixed CC / contribution without S (وبشهر, سپاها, ومعادن)**: wait for the
   CODAL rate limit, then fetch the subscription notice and use
   `pv/nw + (1-pv/nw)(cp/100)(S/P)`; do not infer S from the reference.
2. **Share-only 284**: type the 30 exact-ratio rows from official notices;
   keep `TYPE_UNVERIFIED` until then.
3. **DPS-only 15 worsened**: find independent official amount/date evidence;
   do not add a reference-fitted replacement threshold.
4. **Visual path**: needs an authorized Rahavard session; until then remains
   `BLOCKED_NO_AUTHORIZED_SESSION`.
5. **Silent suites**: the 36 silent entries are listed in the gate; the
   adjustment/fund suites are among them and have standalone counts.

## 9. Limitations

- No visual comparison; the six rows are blocked, not passed.
- The numerical improvement is small (near +0.0249pp), with +1 mismatch; it is
  reported as a data-quality fix, not a broad convergence.
- The 15 worsened rows and 11 near-loss symbols remain open.
- No 100% claim; `docs/audit/ra365-round11-delta.csv` contains the stable-key
  before/after rows.

## 10. Commits and push

- Commit 1 (code/tests): `d9878572157f26b9bf3df6cf4d00be76cbcd453f` — share-noise filter, tests and citation alignment.
- Commit 2 (docs): this report, the visual CSV, the delta CSV and the loop
  history; its SHA is visible in `git log`.
- Push: only `mission/ra365-round11-visual-parity-convergence-2026-10-21`;
  `main`, tags and releases stay untouched.
- Final gate: 139 counted, 36 silent, 0 skipped, 0 failed; protected DB
  unchanged; workdir on D:.
