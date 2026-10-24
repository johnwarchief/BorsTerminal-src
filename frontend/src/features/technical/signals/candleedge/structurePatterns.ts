// Ported from CandleEdge (https://github.com/michaelsboost/CandleEdge),
// commit 75761e26b23ccaf59b31365e1ec817374673d77b,
// src/script.js:442-638, 929-1001.
// Copyright (c) 2026 Michael Schwartz. MIT License (see LICENSE-CANDLEEDGE).
//
// BorsTerminal modifications (documented in CANDLEEDGE-REUSE-AUDIT):
// 1. TypeScript types and detector ids replace the presentation names/icons.
// 2. BOS is evaluated at the confirmation bar of the new swing: the source
//    required `recentHigh.index === idx`, which its own slice makes impossible.
//    The 0.5% threshold is compared as a relative change: the source's
//    `price * 1.005` form makes the exact boundary pass on one side only.
// 3. Liquidity sweeps use the latest confirmed swing level instead of the
//    second-to-last; the original's off-by-one skipped the freshest level.
import type { Candle, PatternBias, SwingPoint } from './types';

export const CANDLEEDGE_STRUCTURE = {
  flatThreshold: 0.03,
  trendThreshold: 0.03,
  doubleTopMaxPriceDiff: 0.04,
  doubleMinSeparation: 5,
  pullback: 0.01,
  bosThreshold: 0.005,
} as const;

export interface LinePattern {
  detector:
    | 'ascending_triangle'
    | 'descending_triangle'
    | 'symmetrical_triangle'
    | 'rising_wedge'
    | 'falling_wedge';
  bias: PatternBias;
  high1: SwingPoint;
  high2: SwingPoint;
  low1: SwingPoint;
  low2: SwingPoint;
}

export interface DoublePattern {
  detector: 'double_top' | 'double_bottom';
  bias: PatternBias;
  first: SwingPoint;
  second: SwingPoint;
}

export interface SwingRelation {
  detector: 'higher_high' | 'higher_low' | 'lower_high' | 'lower_low';
  bias: PatternBias;
  point1: SwingPoint;
  point2: SwingPoint;
}

export interface BosPattern {
  detector: 'bos_bullish' | 'bos_bearish';
  bias: PatternBias;
  brokenLevel: number;
  confirmedAtIndex: number;
  previousSwing: SwingPoint;
  newSwing: SwingPoint;
}

export interface SweepPattern {
  detector: 'liquidity_sweep_high' | 'liquidity_sweep_low';
  bias: PatternBias;
  sweptLevel: number;
  barIndex: number;
  levelSwing: SwingPoint;
}

export function percentSlope(p1: number, p2: number, distance: number): number {
  if (distance <= 0) return 0;
  const pctChange = ((p2 - p1) / p1) * 100;
  return pctChange / distance;
}

export function isRecentlyConfirmed(
  point: SwingPoint,
  currentIdx: number,
  maxBarsAgo = 15,
): boolean {
  if (point.index === undefined) return false;
  return point.index <= currentIdx && currentIdx - point.index <= maxBarsAgo;
}

function lastTwo<T>(items: readonly T[]): [T, T] | null {
  if (items.length < 2) return null;
  return [items[items.length - 2], items[items.length - 1]];
}

function linePattern(
  detector: LinePattern['detector'],
  bias: PatternBias,
  high1: SwingPoint,
  high2: SwingPoint,
  low1: SwingPoint,
  low2: SwingPoint,
): LinePattern {
  return { detector, bias, high1, high2, low1, low2 };
}

export function detectAscendingTriangle(
  highs: readonly SwingPoint[],
  lows: readonly SwingPoint[],
): LinePattern | null {
  const h = lastTwo(highs);
  const l = lastTwo(lows);
  if (!h || !l) return null;
  const [h1, h2] = h;
  const [l1, l2] = l;
  const hSlopePct = percentSlope(h1.price, h2.price, h2.index - h1.index);
  const lSlopePct = percentSlope(l1.price, l2.price, l2.index - l1.index);
  if (
    Math.abs(hSlopePct) < CANDLEEDGE_STRUCTURE.flatThreshold &&
    lSlopePct > CANDLEEDGE_STRUCTURE.trendThreshold &&
    l1.price < h1.price
  ) {
    return linePattern('ascending_triangle', 'bullish', h1, h2, l1, l2);
  }
  return null;
}

export function detectDescendingTriangle(
  highs: readonly SwingPoint[],
  lows: readonly SwingPoint[],
): LinePattern | null {
  const h = lastTwo(highs);
  const l = lastTwo(lows);
  if (!h || !l) return null;
  const [h1, h2] = h;
  const [l1, l2] = l;
  const hSlopePct = percentSlope(h1.price, h2.price, h2.index - h1.index);
  const lSlopePct = percentSlope(l1.price, l2.price, l2.index - l1.index);
  if (
    hSlopePct < -CANDLEEDGE_STRUCTURE.trendThreshold &&
    Math.abs(lSlopePct) < CANDLEEDGE_STRUCTURE.flatThreshold &&
    h2.price > l2.price
  ) {
    return linePattern('descending_triangle', 'bearish', h1, h2, l1, l2);
  }
  return null;
}

export function detectSymmetricalTriangle(
  highs: readonly SwingPoint[],
  lows: readonly SwingPoint[],
): LinePattern | null {
  const h = lastTwo(highs);
  const l = lastTwo(lows);
  if (!h || !l) return null;
  const [h1, h2] = h;
  const [l1, l2] = l;
  const hSlopePct = percentSlope(h1.price, h2.price, h2.index - h1.index);
  const lSlopePct = percentSlope(l1.price, l2.price, l2.index - l1.index);
  if (
    hSlopePct < -CANDLEEDGE_STRUCTURE.trendThreshold &&
    lSlopePct > CANDLEEDGE_STRUCTURE.trendThreshold &&
    h2.price > l2.price
  ) {
    return linePattern('symmetrical_triangle', 'neutral', h1, h2, l1, l2);
  }
  return null;
}

export function detectRisingWedge(
  highs: readonly SwingPoint[],
  lows: readonly SwingPoint[],
): LinePattern | null {
  const h = lastTwo(highs);
  const l = lastTwo(lows);
  if (!h || !l) return null;
  const [h1, h2] = h;
  const [l1, l2] = l;
  const hSlopePct = percentSlope(h1.price, h2.price, h2.index - h1.index);
  const lSlopePct = percentSlope(l1.price, l2.price, l2.index - l1.index);
  if (hSlopePct > 0 && lSlopePct > 0 && hSlopePct < lSlopePct) {
    return linePattern('rising_wedge', 'bearish', h1, h2, l1, l2);
  }
  return null;
}

export function detectFallingWedge(
  highs: readonly SwingPoint[],
  lows: readonly SwingPoint[],
): LinePattern | null {
  const h = lastTwo(highs);
  const l = lastTwo(lows);
  if (!h || !l) return null;
  const [h1, h2] = h;
  const [l1, l2] = l;
  const hSlopePct = percentSlope(h1.price, h2.price, h2.index - h1.index);
  const lSlopePct = percentSlope(l1.price, l2.price, l2.index - l1.index);
  if (hSlopePct < 0 && lSlopePct < 0 && hSlopePct < lSlopePct) {
    return linePattern('falling_wedge', 'bullish', h1, h2, l1, l2);
  }
  return null;
}

export function hasValidPullbackBetweenPeaks(
  candles: readonly Candle[],
  peak1Idx: number,
  peak2Idx: number,
): boolean {
  let lowestBetween = Infinity;
  for (let i = peak1Idx + 1; i < peak2Idx; i += 1) {
    if (candles[i].low < lowestBetween) lowestBetween = candles[i].low;
  }
  const avgPeakPrice = (candles[peak1Idx].high + candles[peak2Idx].high) / 2;
  const pullbackDepth = (avgPeakPrice - lowestBetween) / avgPeakPrice;
  return pullbackDepth > CANDLEEDGE_STRUCTURE.pullback;
}

export function hasValidBounceBetweenTroughs(
  candles: readonly Candle[],
  trough1Idx: number,
  trough2Idx: number,
): boolean {
  let highestBetween = -Infinity;
  for (let i = trough1Idx + 1; i < trough2Idx; i += 1) {
    if (candles[i].high > highestBetween) highestBetween = candles[i].high;
  }
  const avgTroughPrice = (candles[trough1Idx].low + candles[trough2Idx].low) / 2;
  const bounceHeight = (highestBetween - avgTroughPrice) / avgTroughPrice;
  return bounceHeight > CANDLEEDGE_STRUCTURE.pullback;
}

export function detectDoubleTop(
  candles: readonly Candle[],
  peaks: readonly SwingPoint[],
  currentIdx: number,
  confirmationWindow = 15,
): DoublePattern | null {
  if (peaks.length < 2) return null;
  let best: { first: SwingPoint; second: SwingPoint; diff: number } | null = null;

  for (let i = Math.max(0, peaks.length - 20); i < peaks.length - 1; i += 1) {
    for (let j = i + 1; j < peaks.length; j += 1) {
      const first = peaks[i];
      const second = peaks[j];
      const separation = second.index - first.index;
      if (separation < CANDLEEDGE_STRUCTURE.doubleMinSeparation) continue;

      const priceDiff = Math.abs(first.price - second.price) / first.price;
      if (priceDiff > CANDLEEDGE_STRUCTURE.doubleTopMaxPriceDiff) continue;
      if (!hasValidPullbackBetweenPeaks(candles, first.index, second.index)) continue;
      if (!isRecentlyConfirmed(second, currentIdx, confirmationWindow)) continue;

      if (!best || priceDiff < best.diff) best = { first, second, diff: priceDiff };
    }
  }

  if (best) return { detector: 'double_top', bias: 'bearish', first: best.first, second: best.second };
  return null;
}

export function detectDoubleBottom(
  candles: readonly Candle[],
  troughs: readonly SwingPoint[],
  currentIdx: number,
  confirmationWindow = 15,
): DoublePattern | null {
  if (troughs.length < 2) return null;
  let best: { first: SwingPoint; second: SwingPoint; diff: number } | null = null;

  for (let i = Math.max(0, troughs.length - 20); i < troughs.length - 1; i += 1) {
    for (let j = i + 1; j < troughs.length; j += 1) {
      const first = troughs[i];
      const second = troughs[j];
      const separation = second.index - first.index;
      if (separation < CANDLEEDGE_STRUCTURE.doubleMinSeparation) continue;

      const priceDiff = Math.abs(first.price - second.price) / first.price;
      if (priceDiff > CANDLEEDGE_STRUCTURE.doubleTopMaxPriceDiff) continue;
      if (!hasValidBounceBetweenTroughs(candles, first.index, second.index)) continue;
      if (!isRecentlyConfirmed(second, currentIdx, confirmationWindow)) continue;

      if (!best || priceDiff < best.diff) best = { first, second, diff: priceDiff };
    }
  }

  if (best) {
    return { detector: 'double_bottom', bias: 'bullish', first: best.first, second: best.second };
  }
  return null;
}

export function detectHigherHigh(swings: {
  highs: readonly SwingPoint[];
  lows: readonly SwingPoint[];
}): SwingRelation | null {
  const h = lastTwo(swings.highs);
  if (!h) return null;
  const [first, second] = h;
  if (second.price > first.price) {
    return { detector: 'higher_high', bias: 'bullish', point1: first, point2: second };
  }
  return null;
}

export function detectLowerLow(swings: {
  highs: readonly SwingPoint[];
  lows: readonly SwingPoint[];
}): SwingRelation | null {
  const l = lastTwo(swings.lows);
  if (!l) return null;
  const [first, second] = l;
  if (second.price < first.price) {
    return { detector: 'lower_low', bias: 'bearish', point1: first, point2: second };
  }
  return null;
}

export function detectHigherLow(swings: {
  highs: readonly SwingPoint[];
  lows: readonly SwingPoint[];
}): SwingRelation | null {
  const l = lastTwo(swings.lows);
  if (!l) return null;
  const [first, second] = l;
  if (second.price > first.price) {
    return { detector: 'higher_low', bias: 'bullish', point1: first, point2: second };
  }
  return null;
}

export function detectLowerHigh(swings: {
  highs: readonly SwingPoint[];
  lows: readonly SwingPoint[];
}): SwingRelation | null {
  const h = lastTwo(swings.highs);
  if (!h) return null;
  const [first, second] = h;
  if (second.price < first.price) {
    return { detector: 'lower_high', bias: 'bearish', point1: first, point2: second };
  }
  return null;
}

export function detectBosBullish(
  swings: { highs: readonly SwingPoint[]; lows: readonly SwingPoint[] },
  confirmationIndex: number,
  thresholdPct = CANDLEEDGE_STRUCTURE.bosThreshold,
): BosPattern | null {
  const h = lastTwo(swings.highs);
  if (!h) return null;
  const [previousSwing, newSwing] = h;
  if (newSwing.confirmedAtIndex !== confirmationIndex) return null;
  const change = (newSwing.price - previousSwing.price) / previousSwing.price;
  if (!(change > thresholdPct)) return null;
  return {
    detector: 'bos_bullish',
    bias: 'bullish',
    brokenLevel: previousSwing.price,
    confirmedAtIndex: confirmationIndex,
    previousSwing,
    newSwing,
  };
}

export function detectBosBearish(
  swings: { highs: readonly SwingPoint[]; lows: readonly SwingPoint[] },
  confirmationIndex: number,
  thresholdPct = CANDLEEDGE_STRUCTURE.bosThreshold,
): BosPattern | null {
  const l = lastTwo(swings.lows);
  if (!l) return null;
  const [previousSwing, newSwing] = l;
  if (newSwing.confirmedAtIndex !== confirmationIndex) return null;
  const change = (previousSwing.price - newSwing.price) / previousSwing.price;
  if (!(change > thresholdPct)) return null;
  return {
    detector: 'bos_bearish',
    bias: 'bearish',
    brokenLevel: previousSwing.price,
    confirmedAtIndex: confirmationIndex,
    previousSwing,
    newSwing,
  };
}

function latestConfirmedLevel(
  swings: readonly SwingPoint[],
  idx: number,
): SwingPoint | null {
  for (let i = swings.length - 1; i >= 0; i -= 1) {
    const point = swings[i];
    if (point.index < idx && point.confirmedAtIndex <= idx) return point;
  }
  return null;
}

export function detectLiquiditySweepHigh(
  candles: readonly Candle[],
  idx: number,
  swings: { highs: readonly SwingPoint[]; lows: readonly SwingPoint[] },
): SweepPattern | null {
  const candle = candles[idx];
  const level = latestConfirmedLevel(swings.highs, idx);
  if (!candle || !level) return null;
  if (candle.high > level.price && candle.close < level.price) {
    return {
      detector: 'liquidity_sweep_high',
      bias: 'bearish',
      sweptLevel: level.price,
      barIndex: idx,
      levelSwing: level,
    };
  }
  return null;
}

export function detectLiquiditySweepLow(
  candles: readonly Candle[],
  idx: number,
  swings: { highs: readonly SwingPoint[]; lows: readonly SwingPoint[] },
): SweepPattern | null {
  const candle = candles[idx];
  const level = latestConfirmedLevel(swings.lows, idx);
  if (!candle || !level) return null;
  if (candle.low < level.price && candle.close > level.price) {
    return {
      detector: 'liquidity_sweep_low',
      bias: 'bullish',
      sweptLevel: level.price,
      barIndex: idx,
      levelSwing: level,
    };
  }
  return null;
}
