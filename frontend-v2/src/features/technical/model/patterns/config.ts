// model/patterns/config.ts
export interface PatternConfig {
  pivLeft: number;
  pivRight: number;
  atrPeriod: number;
  minTouchesPerLine: number;
  touchToleranceAtr: number;
  invalidationBufferAtr: number;
  /** نیم‌پنجرهٔ حذف هم‌پوشانی: ادامه‌دهندهٔ لنگرِ نزدیک‌تر از این مقدار کندل به یک بازگشتی حذف می‌شود. */
  overlapWindowBars: number;
  outcomeHorizon: number;
  returnHorizons: [number, number, number];
  returnsMinSamples: number;
  neutralMinTargetAtr: number;
  formationMinResolved: number;
  expiryGraceBars: number;
  expiryMinPoints: number;
  flag: { impulseLegAtrMin: number; channelMaxWidthPct: number; slopeOpposite: boolean; maxBars: number; minLegBars: number };
  pennant: { impulseLegAtrMin: number; convergenceMin: number; maxBars: number };
  triangle: { flatToleranceAtr: number; convergenceMin: number; maxBars: number; minSpan: number };
  rectangle: { flatToleranceAtr: number; maxBars: number };
  wedge: { convergenceMin: number; maxBars: number };
  hs: { headAboveShouldersAtr: number; shouldersToleranceAtr: number; maxBars: number };
  triple: { levelToleranceAtr: number; maxBars: number };
  reversal: { minSpanBars: number };
  cup: { rimToleranceAtr: number; handleDepthPct: number; minBars: number; maxBars: number };
  rounding: { curvatureMin: number; minBars: number; maxBars: number };
  tier2: { diamondConvergeMin: number; broadeningMin: number; islandGapAtr: number; threePeaksToleranceAtr: number };
}

export const PATTERN_CONFIG: PatternConfig = {
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
  cup: { rimToleranceAtr: 0.5, handleDepthPct: 33, minBars: 20, maxBars: 160 },
  rounding: { curvatureMin: 0.55, minBars: 30, maxBars: 200 },
  tier2: { diamondConvergeMin: 0.25, broadeningMin: 0.25, islandGapAtr: 0.5, threePeaksToleranceAtr: 0.5 },
};
