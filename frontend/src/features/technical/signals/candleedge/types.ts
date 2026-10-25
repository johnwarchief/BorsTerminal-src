export type CandleTime = number | string;

export interface Candle {
  time: CandleTime;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export type DetectorId =
  | 'doji'
  | 'bullish_engulfing'
  | 'bearish_engulfing'
  | 'hammer'
  | 'shooting_star'
  | 'double_top'
  | 'double_bottom'
  | 'ascending_triangle'
  | 'descending_triangle'
  | 'symmetrical_triangle'
  | 'rising_wedge'
  | 'falling_wedge'
  | 'higher_high'
  | 'higher_low'
  | 'lower_high'
  | 'lower_low'
  | 'bos_bullish'
  | 'bos_bearish'
  | 'liquidity_sweep_high'
  | 'liquidity_sweep_low';

export type PatternFamily = 'candlestick' | 'chart_structure' | 'market_structure';

export type PatternBias = 'bullish' | 'bearish' | 'neutral';

export interface SwingPoint {
  index: number;
  time: CandleTime;
  price: number;
  confirmedAtIndex: number;
}

export interface ProvisionalSwing {
  status: 'provisional';
  detector: 'swing_high' | 'swing_low';
  index: number;
  time: CandleTime;
  price: number;
  confirmedAtIndex: null;
}

export interface PatternAnchor {
  index: number;
  time: CandleTime;
  price: number;
  role: 'candle' | 'high' | 'low' | 'peak' | 'trough';
  /** Bar at which this anchor became knowable (a pivot needs its right window). */
  confirmedAtIndex?: number;
}

export interface PatternEvent {
  key: string;
  detector: DetectorId;
  family: PatternFamily;
  bias: PatternBias;
  status: 'confirmed';
  confirmedAtIndex: number;
  confirmedAt: CandleTime;
  startIndex: number;
  anchors: PatternAnchor[];
  level?: number;
}

export interface ScanOptions {
  swingWindow?: number;
  extremumLookback?: number;
  trendPeriod?: number;
  /**
   * Minimum close penetration beyond the broken level for BOS, as a fraction
   * (0 = the source's 0.5% HH-distance filter retired; strict close through).
   */
  bosThreshold?: number;
}

export interface ScanResult {
  events: PatternEvent[];
  swings: { highs: SwingPoint[]; lows: SwingPoint[] };
  provisionalSwings: ProvisionalSwing[];
}
