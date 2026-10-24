// Ported from CandleEdge (https://github.com/michaelsboost/CandleEdge),
// commit 75761e26b23ccaf59b31365e1ec817374673d77b, src/script.js:409-436.
// Copyright (c) 2026 Michael Schwartz. MIT License (see LICENSE-CANDLEEDGE).
// Modified for BorsTerminal: confirmedAtIndex metadata and a provisional tail scan.
import type { Candle, ProvisionalSwing, SwingPoint } from './types';

export function findSwingPoints(
  candles: readonly Candle[],
  windowSize = 3,
): { highs: SwingPoint[]; lows: SwingPoint[] } {
  const highs: SwingPoint[] = [];
  const lows: SwingPoint[] = [];
  if (windowSize < 1) return { highs, lows };

  for (let i = windowSize; i < candles.length - windowSize; i += 1) {
    let isHigh = true;
    let isLow = true;
    for (let j = -windowSize; j <= windowSize; j += 1) {
      if (j === 0) continue;
      if (candles[i].high <= candles[i + j].high) isHigh = false;
      if (candles[i].low >= candles[i + j].low) isLow = false;
    }
    if (isHigh) {
      highs.push({
        index: i,
        price: candles[i].high,
        time: candles[i].time,
        confirmedAtIndex: i + windowSize,
      });
    }
    if (isLow) {
      lows.push({
        index: i,
        price: candles[i].low,
        time: candles[i].time,
        confirmedAtIndex: i + windowSize,
      });
    }
  }
  return { highs, lows };
}

export function findLocalExtrema(
  candles: readonly Candle[],
  lookback = 5,
): { peaks: SwingPoint[]; troughs: SwingPoint[] } {
  const peaks: SwingPoint[] = [];
  const troughs: SwingPoint[] = [];
  if (lookback < 1) return { peaks, troughs };

  for (let i = lookback; i < candles.length - lookback; i += 1) {
    let isPeak = true;
    let isTrough = true;
    for (let j = 1; j <= lookback; j += 1) {
      if (candles[i].high <= candles[i - j].high || candles[i].high <= candles[i + j].high) {
        isPeak = false;
      }
      if (candles[i].low >= candles[i - j].low || candles[i].low >= candles[i + j].low) {
        isTrough = false;
      }
    }
    if (isPeak) {
      peaks.push({
        index: i,
        price: candles[i].high,
        time: candles[i].time,
        confirmedAtIndex: i + lookback,
      });
    }
    if (isTrough) {
      troughs.push({
        index: i,
        price: candles[i].low,
        time: candles[i].time,
        confirmedAtIndex: i + lookback,
      });
    }
  }
  return { peaks, troughs };
}

function isExtremum(
  candles: readonly Candle[],
  index: number,
  windowSize: number,
  kind: 'high' | 'low',
): boolean {
  for (let j = -windowSize; j <= windowSize; j += 1) {
    if (j === 0) continue;
    const other = index + j;
    if (other < 0 || other >= candles.length) continue;
    if (kind === 'high' && candles[index].high <= candles[other].high) return false;
    if (kind === 'low' && candles[index].low >= candles[other].low) return false;
  }
  return true;
}

/**
 * BorsTerminal adapter: the last `windowSize` bars cannot be confirmed yet.
 * Candidates are exposed with status `provisional` and no confirmation index;
 * they may disappear or become confirmed when later bars arrive.
 */
export function findProvisionalSwings(
  candles: readonly Candle[],
  windowSize = 3,
): ProvisionalSwing[] {
  if (windowSize < 1 || candles.length === 0) return [];
  const start = Math.max(windowSize, candles.length - windowSize);
  const out: ProvisionalSwing[] = [];
  for (let i = start; i < candles.length; i += 1) {
    if (isExtremum(candles, i, windowSize, 'high')) {
      out.push({
        status: 'provisional',
        detector: 'swing_high',
        index: i,
        time: candles[i].time,
        price: candles[i].high,
        confirmedAtIndex: null,
      });
    }
    if (isExtremum(candles, i, windowSize, 'low')) {
      out.push({
        status: 'provisional',
        detector: 'swing_low',
        index: i,
        time: candles[i].time,
        price: candles[i].low,
        confirmedAtIndex: null,
      });
    }
  }
  return out;
}
