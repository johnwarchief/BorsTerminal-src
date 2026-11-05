// model/patterns/__tests__/config.test.ts
import { describe, expect, it } from 'vitest';
import { PATTERN_CONFIG } from '../config';

describe('PATTERN_CONFIG', () => {
  it('pins every default threshold and window exactly as specified in the brief', () => {
    expect(PATTERN_CONFIG).toEqual({
      pivLeft: 5,
      pivRight: 4,
      atrPeriod: 14,
      minTouchesPerLine: 2,
      touchToleranceAtr: 0.5,
      invalidationBufferAtr: 0.5,
      overlapWindowBars: 3,
      outcomeHorizon: 10,
      returnHorizons: [1, 3, 5],
      returnsMinSamples: 5,
      neutralMinTargetAtr: 0.5,
      formationMinResolved: 8,
      expiryGraceBars: 1,
      expiryMinPoints: 5,
      flag: { impulseLegAtrMin: 3.0, channelMaxWidthPct: 35, slopeOpposite: true, maxBars: 40, minLegBars: 3 },
      pennant: { impulseLegAtrMin: 3.0, convergenceMin: 0.35, maxBars: 30 },
      triangle: { flatToleranceAtr: 0.35, convergenceMin: 0.30, maxBars: 60, minSpan: 3 },
      rectangle: { flatToleranceAtr: 0.50, maxBars: 80 },
      wedge: { convergenceMin: 0.30, maxBars: 60 },
      hs: { headAboveShouldersAtr: 0.50, shouldersToleranceAtr: 0.60, maxBars: 120 },
      triple: { levelToleranceAtr: 0.50, maxBars: 120 },
      reversal: { minSpanBars: 6 },
      cup: { rimToleranceAtr: 0.5, handleDepthPct: 33, minDepthAtr: 2, minBars: 20, maxBars: 160 },
      rounding: { curvatureMin: 0.55, minDepthAtr: 1, minBulgeAtr: 1, endSkewPct: 50, minBars: 30, maxBars: 200 },
      tier2: { diamondConvergeMin: 0.25, broadeningMin: 0.25, islandGapAtr: 0.5, islandMaxBlockBars: 5, islandMaxBars: 6, threePeaksToleranceAtr: 0.5 },
    });
  });

  it('pins the tier-2 and cup/rounding defaults', () => {
    expect(PATTERN_CONFIG.cup).toEqual({ rimToleranceAtr: 0.5, handleDepthPct: 33, minDepthAtr: 2, minBars: 20, maxBars: 160 });
    expect(PATTERN_CONFIG.rounding).toEqual({ curvatureMin: 0.55, minDepthAtr: 1, minBulgeAtr: 1, endSkewPct: 50, minBars: 30, maxBars: 200 });
    expect(PATTERN_CONFIG.tier2).toEqual({ diamondConvergeMin: 0.25, broadeningMin: 0.25, islandGapAtr: 0.5, islandMaxBlockBars: 5, islandMaxBars: 6, threePeaksToleranceAtr: 0.5 });
  });
});
