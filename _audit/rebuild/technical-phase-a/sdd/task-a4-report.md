# Task A4 report — Accuracy hardening, registration and tier table

**Status:** complete (local only, no push)
**Commit:** `a42f1550` (parent `e7562c3a`)
**Branch:** `integration/4axes-main-2026-11-03`

## Files

- Modify `frontend-v2/src/features/technical/model/patterns/registry.ts`
  - New `PATTERN_TIER: Record<PatternKind, PatternTier>` (26 kinds: 19 tier-1, 7 tier-2, exactly the brief's table). `Record<PatternKind, …>` makes the table compile-time exhaustive.
  - `detectAllPatterns` merge now includes `detectCupRounding(candles, atr, config)` and `detectTier2(candles, atr, config)`.
  - Every surviving pattern gets `tier: PATTERN_TIER[p.kind]` after the R-PAT-6 overlap filter, so the table is the single runtime authority (detectors still declare their own tier; the central map overrides it with the same value).
  - `fromDoubleTap` now emits `tier: 1`; geometry, id, anchor, boundaries, target, stop, quality and status mapping are unchanged.
- Create `frontend-v2/src/features/technical/model/patterns/__tests__/accuracy.test.ts` — 24 tests: tier assignment, no look-ahead, an 11-row negative table, a 10-row registration/tier table, and overlap priority.
- No change to `geometry.ts`: `emitPattern` already accepts a single-point list (it only requires `points[points.length - 1]` to exist), and the A3 island tests plus the new `series(300)` island prove it in the registry path.

No other detector, config, store or overlay file was touched. Every threshold used by the new tests comes from `PATTERN_CONFIG` (`atrPeriod`, `overlapWindowBars`); no numeric gate was duplicated in the registry.

## Red (before implementation)

Command: `cd frontend-v2 && npx vitest run src/features/technical/model/patterns/__tests__/accuracy.test.ts`

```
 ❯ src/features/technical/model/patterns/__tests__/accuracy.test.ts (24 tests | 12 failed) 65ms
   × assigns a tier to every emitted pattern 25ms
     → Cannot read properties of undefined (reading 'DOUBLE_TOP')
   ✓ never changes an event when later bars are removed
   ✓ rejects CUP_HANDLE when the rim gap exceeds cup.rimToleranceAtr
   ... (all 11 negative rows pass: the detectors were not registered yet)
   × registers CUP_HANDLE with tier 1 through detectAllPatterns
     → CUP_HANDLE: expected undefined to be defined
   ... (all 10 registration rows fail; also INVERSE_CUP_HANDLE, ROUNDING_TOP/BOTTOM,
        DIAMOND_TOP/BOTTOM, BROADENING_TOP/BOTTOM, ISLAND_REVERSAL, THREE_RISING_PEAKS)
   × keeps the reversal when a continuation overlaps it
     → expected undefined to be defined
 Test Files  1 failed (1)
      Tests  12 failed | 12 passed (24)
```

The red drivers are the missing `PATTERN_TIER` export (undefined → TypeError on the first pattern), the two unregistered detectors (registration rows and the tier-2 diamond in the overlap fixture), and the unreachable tier-2 table. The negative rows pass before registration by design: they are regression guards that a freshly registered detector must not start firing on an adversarial series.

## Green

```
npx vitest run src/features/technical/model/patterns/__tests__/accuracy.test.ts
 ✓ accuracy.test.ts (24 tests)
 Test Files  1 passed (1)
      Tests  24 passed (24)

npx vitest run src/features/technical/model/patterns
 Test Files  12 passed (12)
      Tests  121 passed (121)   (was 97 before A4)

npx vitest run                (frontend-v2, full suite)
 Test Files  86 passed (86)
      Tests  719 passed (719)  (was 695 before A4)

npx tsc --noEmit
TSC_EXIT=0
```

## Test inventory

1. `assigns a tier to every emitted pattern` — `detectAllPatterns(series(300), PATTERN_CONFIG)` is non-empty and every pattern's `tier` equals `PATTERN_TIER[kind]` (stronger than the brief's `[1, 2]` membership: a wrong row fails). The series carries a double top (tier 1, adapter) and a tail island (tier 2, detector), so both tiers are exercised through the registry.
2. `never changes an event when later bars are removed` — brief's code verbatim; `series(250)` is a strict prefix of `series(300)` because the path builder's value at index `i` does not depend on `n`. The tail island is anchored at 295, outside the `< 250` window.
3. Negative table — one adversarial series per kind; see mapping below. Test titles include the violated rule (`rejects %s when %s`), as required.
4. `registers %s with tier %i through detectAllPatterns` — one positive fixture per newly registered kind (10 rows), asserting presence and the exact tier. `THREE_FALLING_PEAKS` is intentionally absent; see residual risk 1.
5. `keeps the reversal when a continuation overlaps it` — brief's two assertions plus non-vacuity: `detectContinuation` on the same candles really emits a continuation anchored on the diamond's anchor, and the registry contains none of those raw overlapping ids. Uses `PATTERN_CONFIG.overlapWindowBars` instead of the literal 3.

## Fixture → violated rule (negative table)

| Fixture | Bars | Kind(s) asserted absent | The single violated rule | Evidence it passes everything else |
|---|---|---|---|---|
| `wideRimCup()` | 111 | `CUP_HANDLE` | `|leftRim − rightRim| = 4 > cup.rimToleranceAtr·ATR` | `alignedRimCup()` is the same shape with both rims at 100 and emits `CUP_HANDLE` (tier 1); depth 18 ≥ 2·ATR, span 80 ∈ [20, 160], handle depth 3.55–5.8 ≤ 33 % of depth |
| `wideRimInverseCup()` | 111 | `INVERSE_CUP_HANDLE` | same rim gate, mirrored | `alignedRimInverseCup()` emits `INVERSE_CUP_HANDLE` (tier 1) |
| `vBottom()` | 60 | `ROUNDING_BOTTOM` | 9 of 20 middle-third closes beyond the rim (0.45 < `rounding.curvatureMin` 0.55) | Same V geometry as `V_CLOSES`, which `cupRounding.test.ts` proves emits when `curvatureMin` is lowered; depth 5 ≥ `minDepthAtr`·ATR, bulge 5 > 1·ATR, end skew 2 ≤ 50 % of depth |
| `vTop()` | 60 | `ROUNDING_TOP` | same curvature gate, mirrored | `BOWL_CLOSES` mirror emits `ROUNDING_TOP` (registration row) |
| `wideningFive()` | 120 | `DIAMOND_TOP`, `DIAMOND_BOTTOM` | width end 24.8/21.8 > 0.75·start 6.8/15.8 (`diamondConvergeMin`) | The same two five-pivot windows satisfy `end ≥ 1.25·start` and are emitted as `BROADENING_TOP`/`BROADENING_BOTTOM` (registration rows) |
| `convergingFive()` | 120 | `BROADENING_TOP`, `BROADENING_BOTTOM` | width end 5.8/6.5 < 1.25·start 10.8/17.8 (`broadeningMin`) | The top window is a valid `DIAMOND_TOP` (registration row); the bottom window narrows |
| `oneSidedGap()` | 20 | `ISLAND_REVERSAL` | entry gap 1.8 ≥ `islandGapAtr`·ATR but every exit bar inside `islandMaxBlockBars` stays above `blockLow − gap` | Island is anchored at 19, so it is inside the `maxBars + grace` survival window; absence is the gate, not expiry |
| `spreadPeaks()` | 120 | `THREE_RISING_PEAKS`, `THREE_FALLING_PEAKS` | high trio spread 10.0 > `threePeaksToleranceAtr`·ATR ≈ 0.48; low trio spread 4.0 > same | `levelPeaks()` (spread 0.2) emits `THREE_RISING_PEAKS` (tier 2); the mirrored three-peak trio is covered in `tier2.test.ts` |

Each fixture is a noise-free piecewise-linear path with `high = close + 0.4`, `low = close − 0.4`, so the ATR the registry computes is deterministic; no pivot window is shrunk (the tests run with the production `pivLeft = 5`, `pivRight = 4`).

## Residual risks / concerns

1. **`THREE_FALLING_PEAKS` is unreachable through `detectAllPatterns`.** Its window (three same-kind pivots within `threePeaksToleranceAtr` = 0.5·ATR) necessarily also satisfies `TRIPLE_BOTTOM`'s `levelToleranceAtr` = 0.5·ATR on the same five pivots and the same anchor; the R-PAT-6 reversal-over-continuation filter therefore always drops it. The detector itself is registered and covered at detector level with tier 2 in `tier2.test.ts`, but the brief's "detectAllPatterns includes the seven tier-2 kinds" holds for six of seven. Changing this needs an explicit rule decision (e.g., family/tolerance divergence), not a registry tweak.
2. **The no-look-ahead fixture's tier-2 proof is a tail island.** Islands older than `islandMaxBars + expiryGraceBars` are dropped by `emitPattern`, so the 300-bar series can only exercise `ISLAND_REVERSAL` at the very end. The test is still meaningful for tiers 1 and 2, but it does not exercise old tier-2 shapes.
3. **Negative fixtures are tightly tuned to `PATTERN_CONFIG`.** They encode exact pivot prices and margins (e.g., 4 vs ~0.45 rim tolerance, 9/20 vs 0.55 curvature share). A future threshold change may flip a row to a *passing* adversarial series (test stays green but stops guarding) or make a fixture emit the kind (red for the right reason). Re-check the margins when config changes.
4. **`fromDoubleTap` now carries `tier`.** Downstream consumers that deep-equal the adapted object will see one new field; all existing tests are property-based and unchanged. The brief requires this field.
5. **Overlap test imports `detectContinuation` + `calculateAtr`.** The extra assertions prove non-vacuity against the real detector; they assume the registry computes ATR at the last bar the same way (it does).
6. **`detectAllPatterns` cost grows.** Two more detectors sweep all candles on every call (rounding always scans the last 200 bars). No benchmark was added; the existing store tests stay under their time budget.
7. **The central tier map overrides detector-declared tier.** Intentional single source of truth; if a detector's inline tier ever disagrees with the table, the table wins silently. The registration rows would catch a wrong table value for the listed kinds.
8. **`series(300)` is pinned by behaviour, not by an exact pattern inventory.** Today it emits exactly one double top (tier 1) and one tail island (tier 2); the tier test only requires each emitted pattern's tier to match the table, so a future detector change may add patterns there without failing the test. That is deliberate: the test guards tier delivery, while the registration rows pin which kinds must be reachable.

## Commit

```
a42f1550 test(technical): سخت‌گیری دقت الگوها و رده‌بندی
 2 files changed, 314 insertions(+), 5 deletions(-)
```

Committed with `git -c user.name=johnwarchief -c user.email=johnwarchief@users.noreply.github.com commit`; registry and accuracy test only (`geometry.ts` untouched). The SDD report file itself is untracked, matching the earlier A1–A3 reports.

---

# Fix round 1

**Status:** items 2, 3 and 4 delivered; item 1 delivered at the detector/rulebook/test level, but the requested `THREE_FALLING_PEAKS` registered row is **blocked by a rule conflict** (proof below) and was not added — it would be a permanently red row.
**Commit:** `b8f4932f` (parent `a42f1550`)
**Branch:** `integration/4axes-main-2026-11-03` (local only)

## Files touched

- `frontend-v2/src/features/technical/model/patterns/detectTier2.ts` — `threePeaks` rewritten to highs only.
- `frontend-v2/src/features/technical/model/patterns/__tests__/tier2.test.ts` — falling-kind fixture and the highs-only regression test.
- `frontend-v2/src/features/technical/model/patterns/__tests__/accuracy.test.ts` — hardened no-look-ahead, near-miss negatives, relaxed-key positive controls.
- `docs/patterns/rulebook.md` — the two three-peaks rows (and the island row's stale «planned in A3» note; the A3 keys exist since `e7562c3a`).

No registry, config, geometry, store or overlay change. The report itself stays untracked: `.superpowers/sdd/.gitignore` ignores the whole tree.

## 1. R-PA-13 — three peaks on highs only

`threePeaks` now scans `pivots.filter((x) => x.kind === 'high')` once and splits the kind by the trio's own trend (`trio[2].price < trio[0].price` → falling, otherwise rising, so equally-high trios are rising and the split needs no new key):

- `THREE_RISING_PEAKS` — three ascending highs, `family: 'reversal'`, `direction: 'bearish'`.
- `THREE_FALLING_PEAKS` — three descending highs, `family: 'continuation'`, `direction: 'bearish'`.

Both share the existing gates unchanged (`threePeaksToleranceAtr` trio spread, ≥ 2 middle lows, trio span ≤ `hs.maxBars`, recency ≥ `n − hs.maxBars`) and the same geometry — `upper` = line through the three highs, `lower` = neckline of the two middle lows, `target = neck − height`, `stop = max(highs) + ATR`; the +10 quality bonus stays on the rising kind. Lows no longer produce any kind. No config key was added or changed.

Tests:

- `tier2.test.ts`: `FALLING_CLOSES` (pivot highs 101.0 / 100.7 / 100.4, lows 96.6 / 97.6, confirmation at bar 18) replaces the mirrored `RISING_CLOSES` fixture; asserts tier 2, bearish, continuation, `confirmed`, and the `upper` endpoints. A second test pins the semantics: `mirrored(RISING_CLOSES)` — whose three level **lows** were the old falling trio — now emits neither three-peak kind.
- `accuracy.test.ts`: `descendingPeaks()` plus `keeps the tier-1 triple when a THREE_FALLING_PEAKS shares its anchor`, which asserts the detector really builds the kind (bearish/continuation) and that the registry keeps the same-anchor `TRIPLE_TOP` instead.

### Open conflict — the registered row cannot pass

Adding `['THREE_FALLING_PEAKS', 2, descendingPeaks()]` fails, and no fixture can fix it:

1. `TRIPLE_TOP` and `THREE_FALLING_PEAKS` read the same five pivots and the same tolerance. Both use `0.5 × ATR` (`triple.levelToleranceAtr` and `tier2.threePeaksToleranceAtr`), both anchor on the third high (`emitPattern` anchors on the last point, and both patterns end on that pivot), and both derive their upper/lower lines from the same pivots.
2. A strictly descending high trio cannot be tighter than the triple's `reversal.minSpanBars = 6`: two pivot highs closer than `pivLeft + 1` bars overlap each other's windows, which forces equal highs. The tightest strictly-descending trio therefore spans ≥ 12 bars, so the triple window is always legal.
3. R-PAT-6 (`registry.ts`) drops every continuation anchored within `overlapWindowBars` of a reversal. The triple is a tier-1 reversal at the identical anchor, so the continuation is always the one dropped.

Evidence: a sweep over 304 descending-high shapes (high gaps 5/7/9, drops 0.1–0.4, low depths 6/8/10/12, tails 10/20/40) produced 304 `THREE_FALLING_PEAKS` at `detectTier2` level and **0** through `detectAllPatterns`. A vertical mirror does not help either: under highs-only, mirroring turns the three descending highs into ascending ones (a mirrored series' highs are the original lows), i.e. back into `THREE_RISING_PEAKS`.

So the A4 spec line «`detectAllPatterns` includes the seven tier-2 kinds» still holds for six of seven — the collision moved from `TRIPLE_BOTTOM` to `TRIPLE_TOP`; it did not disappear. Fixing it needs a rule decision outside this fix round's file scope: (a) accept 6/7 and reword the A4 interface, (b) let R-PAT-6 keep a continuation whose anchor coincides with a *different* pattern kind (accepting two labels on one window), or (c) give the continuation a distinct recency/tolerance window. Until one is ruled, `accuracy.test.ts` keeps the 10-row table and the collision test above, which turns red the moment the filter changes — that is the signal to re-add the row.

## 2. R-PA-14 — no-look-ahead

New fixture `lookAheadSeries(n)` (prefix-consistent by construction): a double top at 10..50, a broadening top whose fifth pivot sits at **97 — exactly three bars before the 100 cut** — and a tail island at 295. Two tests:

- `never changes a recorded event when later bars are removed` — sweeps cuts **100 / 120 / 160 / 250**, filters `anchor.index <= cut − PATTERN_CONFIG.pivRight` (5 events at cut 100, 6 at the others), asserts `past.length > 0` and `truncated.length > 0` per cut, then compares, for every past event, `id`, `kind`, `family`, `direction`, `anchor`, all `points` (index + price) and both boundary lines. Status/`breakoutIndex` are compared when the outcome was already determined before the cut (`confirmed` with `breakoutIndex < cut`); `forming`/`invalidated` are deliberately excluded because they depend on bars after the anchor — a pattern anchored at 89 may legitimately be invalidated at 101.
- `never reaches a pivot that a truncated history cannot confirm` — the tripwire. With the full series the 97 pivot is real and `BROADENING_TOP@97` exists; with 100 bars the pivot needs bars 98–101, so no event may be anchored at or after 97.

Sensitivity was verified by mutation: changing `findAlternatingPivots`' loop bound from `i < data.length - right` to `i < data.length` (a look-ahead pivot scan) makes the tripwire test fail and leaves the sweep test green — expected, because the mandated `anchor ≤ cut − pivRight` filter excludes exactly the boundary band the mutation corrupts, which is why the tripwire exists. The mutation was reverted before the commit.

## 3. Negative-fixture strength

Three near-miss fixtures (one violated key, nothing else) plus a positive control that runs the same fixture with the key relaxed:

| Kind(s) | Negative fixture | Violated key | Positive control | Result |
|---|---|---|---|---|
| `DIAMOND_TOP` / `_BOTTOM` | `nearMissDiamond()` / mirror — widths 12.8 → 14.8 → 10.88 (ratio 0.85) | `diamondConvergeMin=0.25` (needs ≤ 0.75×start = 9.6) | same candles, `diamondConvergeMin = 0.1` (bound 11.52) | emits `DIAMOND_TOP@101` / `DIAMOND_BOTTOM@101` |
| `BROADENING_TOP` / `_BOTTOM` | `nearMissBroadening()` / mirror — widths 12.8 → 13.44 → 14.08 (ratio 1.1) | `broadeningMin=0.25` (needs ≥ 1.25×start = 16) | same candles, `broadeningMin = 0.05` (bound 13.44) | emits `BROADENING_TOP@101` / `BROADENING_BOTTOM@101` |
| `ISLAND_REVERSAL` | `nearMissExitGap()` — entry gap 1.6, exit gap 0.3 vs threshold 0.507 | `islandGapAtr=0.5` | same candles, `islandGapAtr = 0.25` (threshold ≈ 0.25) | emits `ISLAND_REVERSAL@18` |

The controls go through `detectAllPatterns` with `{ ...PATTERN_CONFIG, tier2: { ...tier2, <key> } }` and assert absent-then-present, so the key — not some other gate — is what blocks each fixture.

**Where a relaxed key cannot flip the fixture** (reported instead of forced):

- `wideningFive()` as a `DIAMOND_TOP/BOTTOM` negative — cannot flip with any legitimate `diamondConvergeMin`. The window is monotonically widening, so `mid > end` (15.8 vs 24.8) fails independently of the threshold; only a nonsensical negative key would let it through. The threshold itself is pinned by `nearMissDiamond()`, and `wideningFive` stays as the cross-shape guard (it is also the `BROADENING_*` positive fixture).
- `convergingFive()` as a `BROADENING_*` negative — same story: the widths shrink (end 5.8 < start 10.8), so the broadening ratio is below 1 and only a negative `broadeningMin` flips it. The threshold is pinned by `nearMissBroadening()`.
- `oneSidedGap()` as an `ISLAND_REVERSAL` negative — cannot flip at **any** positive `islandGapAtr`: the block's own low keeps falling (101.6 → 100.1), so `high_j < blockLow − gap` never holds. It guards the AND semantics (entry gap alone is not enough); the threshold is pinned by `nearMissExitGap()`.

## 4. Corrected margins

| Row | Old text | Measured |
|---|---|---|
| `vBottom()` | 9 of 20 middle-third closes (0.45) | **8 of 20 = 0.40** below the rim; bisecting `curvatureMin` shows the fixture emits at exactly 0.40, so 0.55 is the only gate it violates (depth 5 ≥ 0.8, bulge 5 > 0.8, end skew 2 ≤ 2.5) |
| `wideRimCup()` handle | «handle depth 3.55–5.8 ≤ 33 % of depth» | **handle depth 5.8 at pivot level** (5.0 on closes — the fixture's design value) against a 6.2 limit (33 % × 18.8); only one handle candidate exists, so the old 3.55–5.8 range had no fixture behind it. Rim gap 4.0 vs `rimToleranceAtr·ATR` 0.44; bisecting `rimToleranceAtr` flips the cup at 4.6, so the rim is the gating key |

## Green (fix round 1)

```
npx tsc --noEmit
TSC_EXIT=0

npx vitest run .../__tests__/accuracy.test.ts .../__tests__/tier2.test.ts
 ✓ src/features/technical/model/patterns/__tests__/tier2.test.ts (15 tests)
 ✓ src/features/technical/model/patterns/__tests__/accuracy.test.ts (34 tests)
 Test Files  2 passed (2)
      Tests  49 passed (49)

npx vitest run src/features/technical/model/patterns
 Test Files  12 passed (12)
      Tests  132 passed (132)      (121 before this round)
```

`accuracy.test.ts` grew from 24 to 34 tests (2 case rows added to the negative table, 3 positive controls, 1 tripwire); `tier2.test.ts` from 14 to 15.

## Concerns (fix round 1)

1. **`THREE_FALLING_PEAKS` is still unreachable through `detectAllPatterns`** — now because of `TRIPLE_TOP`, not `TRIPLE_BOTTOM`; see the proof above. The A4 interface «seven tier-2 kinds reachable» is 6/7 until a rule is ruled on.
2. **Negative fixtures are still threshold-tuned.** The near-miss ratios (0.85 of start for the diamond, 1.1 for the broadening, 0.3 vs 0.507 for the island) sit between the production key and the relaxed key; the control catches a *wrong direction* but not a wrong magnitude. Re-check them when `tier2` keys change.
3. **The no-look-ahead sweep is blind within `pivRight` bars of the cut by construction** (the filter the reviewer asked for). The tripwire covers one pivot (97 before the 100 cut) only; a look-ahead that shifts an anchor deeper inside the boundary band would need another tripwire per cut.
4. **Status is not compared for `forming`/`invalidated` events.** That is correct (they legitimately depend on post-cut bars) but it means a detector that pre-confirmed a pattern early would only be caught for `confirmed` events whose breakout precedes the cut.
5. **`threePeaks` emits the rising kind only when the high trio is level**; a downtrend with three clearly lower highs still emits nothing. That matches the existing tolerance gate and R-PA-13, but if the intent was «any three descending highs», it needs a different key — not a tweak.

---

# Fix round 2

**Status:** complete (local only, no push)
**Commit:** `62b65f6f` (parent `b8f4932f`)
**Branch:** `integration/4axes-main-2026-11-03`

## Files touched

- `frontend-v2/src/features/technical/model/patterns/config.ts` — added `tier2.threePeaksSlopeAtr: 0.5`.
- `frontend-v2/src/features/technical/model/patterns/detectTier2.ts` — `threePeaks` now requires strict high progression plus the slope floor; the level-tolerance gate is gone from this detector.
- `frontend-v2/src/features/technical/model/patterns/__tests__/config.test.ts` — exact pins include the new key (full object and `tier2` row).
- `frontend-v2/src/features/technical/model/patterns/__tests__/tier2.test.ts` — truly ascending/descending fixtures, a near-level negative, and span/recency fixtures updated so they still violate only their own gate.
- `frontend-v2/src/features/technical/model/patterns/__tests__/accuracy.test.ts` — new registered rows, new near-level negatives, collision test replaced by a separation guard.
- `docs/patterns/rulebook.md` — rows 51–52 rewritten; the AMBIGUOUS note on the classic source is kept.

No registry, geometry, store or overlay change. The report stays untracked (`.superpowers/sdd/.gitignore`).

## R-PA-15 — strict progression, not level equality

`threePeaks` still scans highs only and keeps ≥2 tween lows, span ≤ `hs.maxBars`, and the recency prefilter. The `spread ≤ threePeaksToleranceAtr·ATR` gate is replaced by:

- `THREE_RISING_PEAKS`: `h3 > h2 > h1` and `h3 − h1 ≥ threePeaksSlopeAtr·ATR`; `family: 'reversal'`, `direction: 'bearish'`.
- `THREE_FALLING_PEAKS`: `h3 < h2 < h1` and `h1 − h3 ≥ threePeaksSlopeAtr·ATR`; `family: 'continuation'`, `direction: 'bearish'`.
- Equal/half-equal highs fit neither branch, so a triple-top-shaped window no longer produces a three-peaks kind.
- `detectReversal` was not touched; level equality remains only in `TRIPLE_TOP`/`TRIPLE_BOTTOM` via `triple.levelToleranceAtr`.

Geometry is unchanged (`upper` = h1→h3, `lower` = first/last tween low, `target = neck − height`, `stop = max(highs) + ATR`, +10 quality bonus on the rising kind).

Because strict descent by ≥ 0.5·ATR is incompatible with a trio level spread ≤ 0.5·ATR, the old `THREE_FALLING_PEAKS` vs `TRIPLE_TOP` collision is structurally impossible: no fixture can build both at one anchor. The former collision test is replaced by `does not build a same-anchor TRIPLE_TOP for a strictly descending trio`, which fails if the level gate ever returns.

## Fixtures and table

- `tier2.test.ts` (ATR = 2, floor = 1.0): `RISING_CLOSES` highs 100.0/100.6/101.4 (h3−h1 = 1.4); `FALLING_CLOSES` highs 102.0/101.0/100.0 (h1−h3 = 2.0); `NEAR_LEVEL_CLOSES` highs 100.0/100.1/100.4 (0.4 < 1.0) asserts neither kind. `THREE_PEAKS_LONG_CLOSES` / `THREE_PEAKS_STALE_CLOSES` now ascend by 2.0 so they still test span and recency rather than the slope floor.
- `accuracy.test.ts` registered table (now 12 rows): `['THREE_RISING_PEAKS', 2, ascendingSeries()]` (highs 100.4/101.4/102.4) and `['THREE_FALLING_PEAKS', 2, descendingSeries()]` (highs 102.4/101.4/100.4), both through `detectAllPatterns`. Negative table gains `nearLevelPeaks()` for both kinds and keeps `spreadPeaks()` as the non-monotone guard.

## Green

```
npx tsc --noEmit
TSC_EXIT=0

npx vitest run src/features/technical/model/patterns
 Test Files  12 passed (12)
      Tests  136 passed (136)   (132 before this round)

focused verbose:
 ✓ registers THREE_RISING_PEAKS with tier 2 through detectAllPatterns
 ✓ registers THREE_FALLING_PEAKS with tier 2 through detectAllPatterns

npx vitest run                (frontend-v2, full suite)
 Test Files  86 passed (86)
      Tests  734 passed (734)  (719 at A4; +11 in fix round 1, +4 here)
```

`accuracy.test.ts` grew 34 → 37 (two near-level negative rows, one registered row net); `tier2.test.ts` grew 15 → 16 (dedicated near-level negative).

## Concerns (fix round 2)

1. **`tier2.threePeaksToleranceAtr` is now dead config.** R-PA-15 only mandated adding the slope key, so the old key stays in `PatternConfig`/`PATTERN_CONFIG` (exact pins included) although no detector reads it; a future config cleanup should retire it. The rulebook no longer cites it.
2. **The near-level negative is magnitude-tuned.** It relies on ATR ≈ 0.9 in that fixture (floor ≈ 0.45) versus a 0.2 high span; a large `atrPeriod` or key change could weaken it, same caveat as the round-1 near-miss rows.
3. **Equal-high trios no longer emit `THREE_RISING_PEAKS`.** Round 1 treated them as rising; under R-PA-15 they emit nothing, which is the intended separation from `TRIPLE_TOP` but is a deliberate behaviour change for level shapes.
4. **Both registered fixtures are strictly monotone on the three pivot highs.** This makes the rows sensitive to the slope key (the previous tolerance gate rejected the same spread > 0.5·ATR), but it also means the table proves reachability, not that the detector rejects near-level trios through the registry — that is covered by the negative rows.
