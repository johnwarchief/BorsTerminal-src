// model/patterns/config.ts
export interface PatternConfig {
  pivLeft: number;
  pivRight: number;
  atrPeriod: number;
  minTouchesPerLine: number;
  invalidationBufferAtr: number;
  outcomeHorizon: number;
  returnHorizons: [number, number, number];
  formationMinResolved: number;
  flag: { impulseLegAtrMin: number; channelMaxWidthPct: number; slopeOpposite: boolean; maxBars: number };
  pennant: { impulseLegAtrMin: number; convergenceMin: number; maxBars: number };
  triangle: { flatToleranceAtr: number; convergenceMin: number; maxBars: number };
  rectangle: { flatToleranceAtr: number; maxBars: number };
  wedge: { convergenceMin: number; maxBars: number };
  hs: { headAboveShouldersAtr: number; shouldersToleranceAtr: number; maxBars: number };
  triple: { levelToleranceAtr: number; maxBars: number };
}

export const PATTERN_CONFIG: PatternConfig = {
  pivLeft: 5,
  pivRight: 4,
  atrPeriod: 14,
  minTouchesPerLine: 2,
  invalidationBufferAtr: 0.5,
  outcomeHorizon: 10,
  returnHorizons: [1, 3, 5],
  formationMinResolved: 8,
  flag: { impulseLegAtrMin: 3.0, channelMaxWidthPct: 35, slopeOpposite: true, maxBars: 40 },
  pennant: { impulseLegAtrMin: 3.0, convergenceMin: 0.35, maxBars: 30 },
  triangle: { flatToleranceAtr: 0.35, convergenceMin: 0.30, maxBars: 60 },
  rectangle: { flatToleranceAtr: 0.50, maxBars: 80 },
  wedge: { convergenceMin: 0.30, maxBars: 60 },
  hs: { headAboveShouldersAtr: 0.50, shouldersToleranceAtr: 0.60, maxBars: 120 },
  triple: { levelToleranceAtr: 0.50, maxBars: 120 },
};
