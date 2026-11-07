export interface EventConfig {
  atrPeriod: number;
  scanWindow: number;
  maxPrimaryPerFamily: number;
  budgetMs: number;
  divergence: {
    rsiPeriod: number;
    pivLeft: number;
    pivRight: number;
    lookbackBars: number;
    minPivotGap: number;
    priceTolAtr: number;
    rsiTol: number;
  };
  channel: {
    lookbackBars: number;
    minBars: number;
    minR2: number;
    minTouches: number;
    touchTolAtr: number;
    directionSlopeAtr: number;
  };
  pullback: {
    emaFast: number;
    emaSlow: number;
    pivLeft: number;
    pivRight: number;
    lookbackBars: number;
    breakoutBufferAtr: number;
    retestTolAtr: number;
    minQuality: number;
  };
  /** p21 — Support/Resistance Retest Breakout (Indi 248). */
  srRetest: {
    pivotLen: number;
    stdevLen: number;
    toleranceStdevMult: number;
    maxZones: number;
    expiryBars: number;
    closeConfirm: boolean;
  };
}

export const EVENT_CONFIG: EventConfig = {
  atrPeriod: 14,
  scanWindow: 500,
  maxPrimaryPerFamily: 1,
  budgetMs: 50,
  divergence: {
    rsiPeriod: 14,
    pivLeft: 3,
    pivRight: 2,
    lookbackBars: 120,
    minPivotGap: 5,
    priceTolAtr: 0.5,
    rsiTol: 2,
  },
  channel: {
    lookbackBars: 120,
    minBars: 40,
    minR2: 0.6,
    minTouches: 2,
    touchTolAtr: 0.5,
    directionSlopeAtr: 0.02,
  },
  pullback: {
    emaFast: 20,
    emaSlow: 50,
    pivLeft: 3,
    pivRight: 2,
    lookbackBars: 500,
    breakoutBufferAtr: 0.25,
    retestTolAtr: 0.5,
    minQuality: 35,
  },
  srRetest: {
    pivotLen: 7,
    stdevLen: 40,
    toleranceStdevMult: 1.0,
    maxZones: 150,
    expiryBars: 500,
    closeConfirm: true,
  },
};
