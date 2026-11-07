# Task A1 report — Rulebook, tier field and new config keys

**Status:** complete (local only, no push)
**Commit:** `6c94099a377460b6b5bed4fa2bfe4d4002855f38`
**Branch:** `integration/4axes-main-2026-11-03`

## Files

- Create `docs/patterns/rulebook.md` — 26 rows (19 tier-1 + 7 tier-2), thresholds copied from `PATTERN_CONFIG`; `AMBIGUOUS` used for diamond's classic broaden-then-contract shape and the three rising/falling family assignments.
- Modify `frontend-v2/src/features/technical/model/patterns/config.ts` — added `cup`, `rounding`, `tier2` blocks (exact brief literals).
- Modify `frontend-v2/src/features/technical/model/patterns/types.ts` — added `PatternTier = 1 | 2`, `ChartPattern.tier?: PatternTier`, and the 11 new `PatternKind` members required by the plan's later detectors (`PATTERN_TIER` is `Record<PatternKind, 1 | 2>` in A4).
- Modify `frontend-v2/src/features/technical/model/patterns/__tests__/config.test.ts` — added the exact-pin `it` from the brief and extended the existing whole-object pin with the three new blocks (extended, not weakened).

## Red

```
FAIL src/features/technical/model/patterns/__tests__/config.test.ts > PATTERN_CONFIG > pins the tier-2 and cup/rounding defaults
AssertionError: expected undefined to deeply equal { rimToleranceAtr: 0.5, …(3) }
- Expected: { "handleDepthPct": 33, "maxBars": 160, "minBars": 20, "rimToleranceAtr": 0.5 }
+ Received: undefined
Tests  1 failed | 1 passed (2)
```

After adding the keys, the existing whole-object `toEqual` failed only on the three new properties (extra keys). That pin was extended with the same literals; no existing assertion was removed or relaxed.

## Green

```
npx vitest run src/features/technical/model/patterns/__tests__/config.test.ts
✓ 2 tests passed

npx vitest run src/features/technical/model/patterns
Test Files  9 passed (9)
Tests       69 passed (69)

npx tsc --noEmit
exit 0
```

Rulebook row audit: 26 data rows; 19 marked tier 1, 7 marked tier 2.

## Residual risks

1. `rounding.curvatureMin=0.55` is now pinned but the phase-A plan's A2 `rounding()` sample does not read it; A2 must consume the key or the rulebook's curvature gate is ahead of the detector.
2. Planned A2/A3 gates contain literals outside `PATTERN_CONFIG` (cup depth `< 2*ATR`, island block 2–5 bars / `maxBars: 6`). Spec §5 says no threshold may live outside `PATTERN_CONFIG`; A2/A3 must move or explicitly justify them.
3. Diamond is implemented as converging-only while the classic diamond broadens then contracts; `THREE_RISING_PEAKS`/`THREE_FALLING_PEAKS` family assignments in the plan are asymmetric. Both are marked `AMBIGUOUS` in the rulebook; A3 must record the ruling the plan asks for.
4. The 11 new `PatternKind` members are a type-level addition beyond A1's one-line interface. They are needed so A2/A3 detectors and A4's `PATTERN_TIER: Record<PatternKind, 1 | 2>` compile; no runtime or visual change.
5. `DOUBLE_TOP`/`DOUBLE_BOTTOM` keep their gates in `DEFAULT_PRECISION_PARAMS` (`tolAtr=0.45`, `minSpan=5`, `maxSpan=80`, `minHeightAtr=1.0`, `nonOverlapBars=10`), outside `PATTERN_CONFIG`, to preserve the existing engine byte-for-byte; the rulebook marks this explicitly.
6. Verification was scoped to the config test, the whole `model/patterns` suite and `tsc --noEmit`; the full frontend suite was not re-run (only a pure type/config change).

## Fix round 1 — rulebook gate honesty

**Status:** complete (local only, no push)
**Commit:** `d5dbfaa5` — `docs(patterns): هم‌تراز کردن دروازه‌های کتاب قواعد با کد` (only `docs/patterns/rulebook.md`)

The review approved the spec but found the rulebook asserting gates that do not exist in the detectors. Docs-only fix; no code or config change.

- `TRIANGLE_ASC` / `TRIANGLE_DESC`: dropped the «عرض همگرا» claim and `triangle.convergenceMin`; both rows now state the flat-tolerance gate (`triangle.flatToleranceAtr` + `l2 > l1` / `h2 < h1`). `convergenceMin` remains only on `TRIANGLE_SYM`, the only branch that reads it (`detectContinuation.ts:238,261`).
- `THREE_RISING_PEAKS` / `THREE_FALLING_PEAKS`: removed «در کد فقط سقف سوم > سقف اول لازم است»; the rule now names `threePeaksToleranceAtr` + ≥2 tween pivots as the gate and `rising` as a +10 quality signal only. Family assignment stays `AMBIGUOUS`.
- `ISLAND_REVERSAL`: exit-within-5-bars and `maxBars=6` are labelled «برنامه‌ریزی‌شده در A3» (not a current gate); the intro no longer calls the island block length a non-gate.
- Source column: rows without a detector now use only `classic` (or `existing-engine`) plus «پیاده‌سازی: A2/A3»; dropped «تشخیص‌دهندهٔ A2» and the bare «ردهٔ ۲ بهترین‌تلاش (A3)» citations. `existing-engine` rows cite the real `detectContinuation` / `detectReversal` / `doubleTapEngine`.
- Added the required top line about `PATTERN_CONFIG` + planned-gate marking, plus a Source legend bullet.

Verification: `grep 'triangle.convergenceMin'` hits only the `TRIANGLE_SYM` row; `grep 'در کد فقط'` empty; 26 data rows (19 tier-1 / 7 tier-2); no `detectCupRounding` / `detectTier2` / «تشخیص‌دهندهٔ A2» citations.
