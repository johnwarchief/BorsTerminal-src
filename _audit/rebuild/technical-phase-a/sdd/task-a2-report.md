# Task A2 report — Cup & handle and rounding detectors (tier 1)

**Status:** complete (local only, no push)
**Commit:** `22d57c21`
**Branch:** `integration/4axes-main-2026-11-03`

## Files

- Create `frontend-v2/src/features/technical/model/patterns/detectCupRounding.ts` — `detectCupRounding(candles, atr, config)`: pivot-based cup / inverse cup and three-section rounding bottom / top. Emits `tier: 1`, family `maxBars` and `invalidationBuffer` on every spec; `lineP`/`flatP`/`pt` are typed `PatternPoint`/`BoundaryLine` with no casts.
- Create `frontend-v2/src/features/technical/model/patterns/__tests__/cupRounding.test.ts` — 8 tests (4 positive kinds, V-notch negative, curvature-share gate proof, two depth-gate config proofs).
- Modify `frontend-v2/src/features/technical/model/patterns/config.ts` — `cup.minDepthAtr: 2`, `rounding.minDepthAtr: 1` (interface + `PATTERN_CONFIG`).
- Modify `frontend-v2/src/features/technical/model/patterns/__tests__/config.test.ts` — exact-pin updated with both new keys (whole-object pin and cup/rounding block pin; no assertion weakened).
- Modify `frontend-v2/src/features/technical/model/patterns/geometry.ts` — `PatternSpec.tier?: PatternTier` and `tier: spec.tier` in the returned `ChartPattern`; required so the brief's `emitPattern({ …, tier: 1 })` typechecks and the field reaches consumers (plan's Type-consistency section explicitly states this).

## Red

Command: `npx vitest run src/features/technical/model/patterns/__tests__/cupRounding.test.ts`

```
FAIL  src/features/technical/model/patterns/__tests__/cupRounding.test.ts [ src/features/technical/model/patterns/__tests__/cupRounding.test.ts ]
Error: Failed to resolve import "../detectCupRounding" from "src/features/technical/model/patterns/__tests__/cupRounding.test.ts". Does the file exist?
  Plugin: vite:import-analysis
  File: .../__tests__/cupRounding.test.ts:3:34
 Test Files  1 failed (1)
      Tests  no tests
```

## Green

```
npx vitest run src/features/technical/model/patterns/__tests__/cupRounding.test.ts src/features/technical/model/patterns/__tests__/config.test.ts
Test Files  2 passed (2)
Tests       10 passed (10)

npx vitest run src/features/technical/model/patterns
Test Files  10 passed (10)
Tests       77 passed (77)

npx vitest run          (frontend-v2, full suite)
Test Files  84 passed (84)
Tests       675 passed (675)

npx tsc -b
exit 0
```

## Fixtures → kind

| Fixture | Shape | Asserts |
|---|---|---|
| `CUP_CLOSES` (60 bars) | left rim 100, bowl bottom 90, right rim 100 (depth 10.8 = 5.4×ATR), handle 97.55 (3.25 = 30% of depth, ≤ 33%), close 102.05 breakout | `CUP_HANDLE`, `confirmed`, `bullish`, `continuation`, `tier 1` |
| mirrored `CUP_CLOSES` | same shape inverted around 200 | `INVERSE_CUP_HANDLE`, `confirmed`, `bearish`, `tier 1` |
| `V_CLOSES` (60 bars) | flat 100, narrow V notch to 94, lower shelf 98; only 9 of the 20 middle-third closes sit below the rim line (share 0.45 < 0.55) | full result `[]` (no cup — rim spread 2.0 > 1.0; no rounding — curvature share fails) |
| `V_CLOSES` with `curvatureMin: 0.4` | same series, loosened gate | `ROUNDING_BOTTOM` appears → proves `curvatureMin` is consumed, not decoration |
| `BOWL_CLOSES` (45 bars) | 100 → 92, parabolic bottom 89 in the middle third, back to 100; depth 3.0 = 1.5×ATR; 13/15 middle closes below rim | `ROUNDING_BOTTOM`, `bullish`, `reversal`, `tier 1` |
| mirrored `BOWL_CLOSES` | saucer top | `ROUNDING_TOP`, `bearish`, `tier 1` |
| `CUP_CLOSES` with `cup.minDepthAtr: 6` | depth gate 12 > actual 10.8 | no `CUP_HANDLE` → `cup.minDepthAtr` is consumed |
| `BOWL_CLOSES` with `rounding.minDepthAtr: 2` | depth gate 4 > actual 3.0 | no `ROUNDING_BOTTOM` → `rounding.minDepthAtr` is consumed |

## R-PA-5 implementation

In the middle third of the window, `shareBeyondRim` counts closes strictly below (bottom) or above (top) the horizontal rim line `(lows(first)+lows(last))/2` / `(highs(first)+highs(last))/2`, evaluated through `lineValue` on a typed `BoundaryLine`. The candidate is rejected unless `share >= config.rounding.curvatureMin`. The V fixture fails at 0.45 and passes when the config is lowered to 0.4 — the test proves the gate is wired to config.

## Deviations from the brief's sketch (disclosed)

1. **Cup fixture bars adjusted.** The brief's 20+30+10+12 series only yields pivots `low → high → low` (one rim, one bottom, one handle low) under `pivLeft/pivRight = 1`, so no cup can ever match; per the method, the fixture bars were reshaped (not thresholds) into `high rim → low → high rim → low handle → breakout`.
2. **Rounding depth is side-specific.** The sketch computes depth from the low side even for a top; `target = midP.price - depth` then overshoots below the rim (e.g. 103.4 instead of the rim 108.4 on the mirrored bowl). Implemented `bottomDepth = bottomRim - lows(middle)` and `topDepth = highs(middle) - topRim`; the bottom path matches the sketch.
3. **V negative fixture** uses a sharp notch on a slightly lower shelf so the cup detector's rim tolerance also rejects it; the assertion is the literal `[]` required by the brief, and the curvature-only coupling is proven by the lowered-threshold test.

## Residual risks

- Detector is not registered yet (A4 owns registry wiring); `detectAllPatterns` does not see these kinds until then.
- `emitPattern` always anchors rounding at the last candle, so rounding patterns surface as `forming`; a breakout state can never be observed for them without a later-bar re-detection design.
- Cup emits even when no handle pivot exists (per brief code); a flat-rim V can look like a handle-less cup. Not tested negatively by contract.
- The curvature share rejects a V whose middle third hugs the rim, but a V spanning the whole window (outer thirds forming the arms) can still pass the share; the gate is a curvature proxy, not a full convexity fit.
- Thresholds are exercised only through synthetic, noise-free fixtures; real-market false-positive rate is unmeasured until the scanner feed (A5/A6).

## Fix round 1

**Status:** complete (local only, no push)
**Commit:** `64ebeea8` (parents `22d57c21`)
**Branch:** `integration/4axes-main-2026-11-03`

Review verdict was spec ✅ / quality Needs fixes (Important-1 cup handle optional, Important-2 literal gates, Important-3 fabricated rounding anchor; Minor target-equals-rim and unbounded handle search). All five are addressed below; only the detector, `config.ts` and their two specs changed.

### 1. R-PA-7 — handle is mandatory

`cups()` no longer accepts `!handle`. The first opposite-kind pivot after the second rim must exist, sit inside `b.index + cup.maxBars` (also closes Minor-5), have `handleDepth > 0`, and satisfy `handleDepth <= handleDepthPct% × cup depth`; otherwise the candidate is skipped (`continue`), for both cup and inverse cup.

Tests (`cupRounding.test.ts`):
- `CUP_NO_HANDLE_CLOSES` — a 100→90→100 U that ends flat on the right rim, so no pivot low follows it; the old branch emitted a forming `CUP_HANDLE`, the new one emits none (straight and mirrored).
- `CUP_DEEP_HANDLE_CLOSES` — same cup with a handle to 95.9 (4.9 = 45% of the 10.8 depth, cap 33%); no `CUP_HANDLE`/`INVERSE_CUP_HANDLE`. This fixture is a guard (the old code already rejected deep handles), not a red test.

### 2. R-PA-8 — no literal gates

`PatternConfig.rounding` / `PATTERN_CONFIG.rounding` gained `minBulgeAtr: 1` and `endSkewPct: 50` (exact-pin test updated: whole-object pin and the cup/rounding block pin). The detector now uses `midLow < min(firstLow, lastLow − minBulgeAtr·atr)` (was `lastLow − atr`) and `|first − last| <= endSkewPct/100 × depth` (was `0.5 × depth`). Defaults reproduce the old numbers, so no fixture semantics changed.

Tests: `rounding.minBulgeAtr: 10` kills the bowl emission; `rounding.endSkewPct: 0` kills the (0.5-skew) late-breakout fixture. Both prove the keys are consumed, not decoration.

### 3+4. R-PA-8 — real extreme anchor, left/right from real extremes, target rim ± depth

`rounding()` now locates, per section, the actual bar of the section extreme (`extremeAt` returns offset + real high/low). Points are built on those real bars: left = first-third extreme, right = last-third extreme, anchor = the middle-third extreme (the pattern's lowest low / highest high). The anchor is the last point (the `emitPattern` contract: it scans the breakout from `anchor.index + 1`), so the breakout scan now starts right after the real bottom/top instead of after `n-1` and can return `confirmed` and an `outcomeOf` window. Boundaries: bottom `upper = line(left, right)` (rim through the two end extremes), `lower = flat(anchor)`; top mirrored. `target = rim ± depth` with `rim = (first extreme + last extreme)/2` (was `midP.price ± depth`, which algebraically equaled the rim); `stopLoss` at the extreme ± atr. Note: `points` order is left, right, anchor — deliberately not chronological, because the emitter anchors on the last point; no other consumer draws `points` (overlay uses `anchor`/boundaries only).

Test: `LATE_BREAKOUT_CLOSES` — rim line 91.6→92.1, bottom 88.6 at bar 26, close 92.2 at bar 29 crosses the rim line exactly 3 bars later. Asserts `anchor.index === 26`, `anchor.price ≈ 88.6`, `status === 'confirmed'`, `breakoutIndex === 29`, `breakoutIndex − anchor.index === 3`. Target test asserts `ROUNDING_BOTTOM.target ≈ 94.6` (91.6 + 3.0) and `ROUNDING_TOP.target ≈ 105.4` (108.4 − 3.0) — the old code returned the rim itself (91.6 / 108.4).

### Red (new specs vs detector at `22d57c21`, same tests)

```
Tests  5 failed | 9 passed (14)
  × requires a handle pivot: a U with no pullback after the right rim is not a CUP_HANDLE
  × anchors ROUNDING_BOTTOM on the real extreme bar and confirms the breakout 3 bars later
      → expected 44 to be 26            (old anchor was n-1)
  × targets rim ± depth beyond the rim, not the rim itself
      → expected 91.6 to be close to 94.6
  × consumes rounding.minBulgeAtr as a real gate
  × consumes rounding.endSkewPct as a real gate
```

### Green

```
npx tsc --noEmit
exit 0

npx vitest run src/features/technical/model/patterns/__tests__/cupRounding.test.ts src/features/technical/model/patterns/__tests__/config.test.ts
 ✓ src/features/technical/model/patterns/__tests__/config.test.ts (2 tests) 10ms
 ✓ src/features/technical/model/patterns/__tests__/cupRounding.test.ts (14 tests) 27ms
 Test Files  2 passed (2)
      Tests  16 passed (16)

npx vitest run src/features/technical/model/patterns
 Test Files  10 passed (10)
      Tests  83 passed (83)
```

### Residual risks (updated)

- The handle-less-U fixture necessarily ends on the right rim: any post-rim pullback that later breaks out confirms as a pivot low with `pivRight`, so a true `!handle` series is a U that has not pulled back yet (forming) — exactly the false positive the old branch emitted.
- Rounding can now surface as `confirmed` with `breakoutIndex` set; the pattern is anchored at its bottom/top, so `selectFeaturedPatterns`/overlap ordering treat it as older than the last bar (intended: the anchor is the pattern origin, matching cups/reversals).
- `points` for rounding is not chronological (anchor last by contract); nothing renders `points` as a polyline today, but a future renderer must not assume ascending order for this kind.
- The cup target was already `rim ± depth`; only rounding's target moved. Thresholds still exercised only on synthetic, noise-free fixtures.
