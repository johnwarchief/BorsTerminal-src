import { isBearishEngulfing, isBullishEngulfing, isDoji, isHammer, isShootingStar } from './candlePatterns';
import { findLocalExtrema, findProvisionalSwings, findSwingPoints } from './swings';
import {
  detectAscendingTriangle,
  detectBosBearish,
  detectBosBullish,
  detectDescendingTriangle,
  detectDoubleBottom,
  detectDoubleTop,
  detectFallingWedge,
  detectHigherHigh,
  detectHigherLow,
  detectLiquiditySweepHigh,
  detectLiquiditySweepLow,
  detectLowerHigh,
  detectLowerLow,
  detectRisingWedge,
  detectSymmetricalTriangle,
} from './structurePatterns';
import type {
  Candle,
  DetectorId,
  PatternAnchor,
  PatternBias,
  PatternEvent,
  PatternFamily,
  ScanOptions,
  ScanResult,
  SwingPoint,
} from './types';
import { assertValidCandles } from './validation';

const DEFAULTS = { swingWindow: 3, extremumLookback: 5, trendPeriod: 20, bosThreshold: 0 };

function positiveInt(value: number | undefined, fallback: number, name: string): number {
  if (value === undefined) return fallback;
  if (!Number.isInteger(value) || value < 1) {
    throw new RangeError(`${name} must be a positive integer`);
  }
  return value;
}

function nonNegative(value: number | undefined, fallback: number, name: string): number {
  if (value === undefined) return fallback;
  if (!Number.isFinite(value) || value < 0) {
    throw new RangeError(`${name} must be a finite number >= 0`);
  }
  return value;
}

interface AnchorSpec {
  index: number;
  price: number;
  role: PatternAnchor['role'];
  confirmedAtIndex?: number;
}

function makeEvent(
  candles: readonly Candle[],
  detector: DetectorId,
  family: PatternFamily,
  bias: PatternBias,
  confirmedAtIndex: number,
  specs: AnchorSpec[],
  level?: number,
): PatternEvent {
  const anchors: PatternAnchor[] = specs.map((spec) => ({
    index: spec.index,
    time: candles[spec.index].time,
    price: spec.price,
    role: spec.role,
    confirmedAtIndex: spec.confirmedAtIndex ?? spec.index,
  }));
  const startIndex = Math.min(...anchors.map((anchor) => anchor.index));
  const event: PatternEvent = {
    key: `${detector}@${confirmedAtIndex}`,
    detector,
    family,
    bias,
    status: 'confirmed',
    confirmedAtIndex,
    confirmedAt: candles[confirmedAtIndex].time,
    startIndex,
    anchors,
  };
  if (level !== undefined) event.level = level;
  return event;
}

function groupByConfirmation(points: readonly SwingPoint[]): Map<number, SwingPoint[]> {
  const grouped = new Map<number, SwingPoint[]>();
  for (const point of points) {
    const bucket = grouped.get(point.confirmedAtIndex);
    if (bucket) bucket.push(point);
    else grouped.set(point.confirmedAtIndex, [point]);
  }
  return grouped;
}

export function scanPatterns(
  candles: readonly Candle[],
  options: ScanOptions = {},
): ScanResult {
  assertValidCandles(candles);
  const swingWindow = positiveInt(options.swingWindow, DEFAULTS.swingWindow, 'swingWindow');
  const extremumLookback = positiveInt(
    options.extremumLookback,
    DEFAULTS.extremumLookback,
    'extremumLookback',
  );
  const trendPeriod = positiveInt(options.trendPeriod, DEFAULTS.trendPeriod, 'trendPeriod');
  const bosThreshold = nonNegative(options.bosThreshold, DEFAULTS.bosThreshold, 'bosThreshold');

  const events = new Map<string, PatternEvent>();
  const push = (event: PatternEvent) => {
    if (!events.has(event.key)) events.set(event.key, event);
  };

  const { highs, lows } = findSwingPoints(candles, swingWindow);
  const { peaks, troughs } = findLocalExtrema(candles, extremumLookback);
  const highAt = groupByConfirmation(highs);
  const lowAt = groupByConfirmation(lows);
  const peakAt = groupByConfirmation(peaks);
  const troughAt = groupByConfirmation(troughs);

  const windowHighs: SwingPoint[] = [];
  const windowLows: SwingPoint[] = [];
  const windowPeaks: SwingPoint[] = [];
  const windowTroughs: SwingPoint[] = [];

  const trimWindow = (points: SwingPoint[], windowStart: number) => {
    while (points.length > 0 && points[0].index < windowStart) points.shift();
  };

  for (let i = 0; i < candles.length; i += 1) {
    const candle = candles[i];

    if (isDoji(candle)) {
      push(
        makeEvent(candles, 'doji', 'candlestick', 'neutral', i, [
          { index: i, price: candle.close, role: 'candle' },
        ]),
      );
    }
    if (isBullishEngulfing(candles, i)) {
      push(
        makeEvent(candles, 'bullish_engulfing', 'candlestick', 'bullish', i, [
          { index: i - 1, price: candles[i - 1].close, role: 'candle' },
          { index: i, price: candle.close, role: 'candle' },
        ]),
      );
    }
    if (isBearishEngulfing(candles, i)) {
      push(
        makeEvent(candles, 'bearish_engulfing', 'candlestick', 'bearish', i, [
          { index: i - 1, price: candles[i - 1].close, role: 'candle' },
          { index: i, price: candle.close, role: 'candle' },
        ]),
      );
    }
    if (isHammer(candles, i, trendPeriod)) {
      push(
        makeEvent(candles, 'hammer', 'candlestick', 'bullish', i, [
          { index: i, price: candle.close, role: 'candle' },
        ]),
      );
    }
    if (isShootingStar(candles, i, trendPeriod)) {
      push(
        makeEvent(candles, 'shooting_star', 'candlestick', 'bearish', i, [
          { index: i, price: candle.close, role: 'candle' },
        ]),
      );
    }

    const addedHighs = highAt.get(i) ?? [];
    const addedLows = lowAt.get(i) ?? [];
    const addedPeaks = peakAt.get(i) ?? [];
    const addedTroughs = troughAt.get(i) ?? [];

    windowHighs.push(...addedHighs);
    windowLows.push(...addedLows);
    windowPeaks.push(...addedPeaks);
    windowTroughs.push(...addedTroughs);

    // CandleEdge only evaluates chart/market structure at idx > 40 and only
    // against swings found in the last 200 bars (src/script.js:1075-1078).
    if (i <= 40) continue;

    trimWindow(windowHighs, i - 200);
    trimWindow(windowLows, i - 200);
    trimWindow(windowPeaks, i - 200);
    trimWindow(windowTroughs, i - 200);

    // BOS is a price crossing, so it is checked on every bar, not only when a
    // new pivot confirms. The level must have been confirmed before this bar.
    const swingsNow = { highs: windowHighs, lows: windowLows };
    const bosBullish = detectBosBullish(candles, i, swingsNow, bosThreshold);
    if (bosBullish) {
      push(
        makeEvent(candles, bosBullish.detector, 'market_structure', bosBullish.bias, i, [
          {
            index: bosBullish.levelSwing.index,
            price: bosBullish.levelSwing.price,
            role: 'high',
            confirmedAtIndex: bosBullish.levelSwing.confirmedAtIndex,
          },
          { index: i, price: candle.close, role: 'candle', confirmedAtIndex: i },
        ], bosBullish.brokenLevel),
      );
    }
    const bosBearish = detectBosBearish(candles, i, swingsNow, bosThreshold);
    if (bosBearish) {
      push(
        makeEvent(candles, bosBearish.detector, 'market_structure', bosBearish.bias, i, [
          {
            index: bosBearish.levelSwing.index,
            price: bosBearish.levelSwing.price,
            role: 'low',
            confirmedAtIndex: bosBearish.levelSwing.confirmedAtIndex,
          },
          { index: i, price: candle.close, role: 'candle', confirmedAtIndex: i },
        ], bosBearish.brokenLevel),
      );
    }

    if (addedHighs.length > 0) {
      const swings = { highs: windowHighs, lows: windowLows };
      const higherHigh = detectHigherHigh(swings);
      if (higherHigh && higherHigh.point2.confirmedAtIndex === i) {
        push(
          makeEvent(candles, higherHigh.detector, 'market_structure', higherHigh.bias, i, [
            {
              index: higherHigh.point1.index,
              price: higherHigh.point1.price,
              role: 'high',
              confirmedAtIndex: higherHigh.point1.confirmedAtIndex,
            },
            {
              index: higherHigh.point2.index,
              price: higherHigh.point2.price,
              role: 'high',
              confirmedAtIndex: higherHigh.point2.confirmedAtIndex,
            },
          ]),
        );
      }
      const lowerHigh = detectLowerHigh(swings);
      if (lowerHigh && lowerHigh.point2.confirmedAtIndex === i) {
        push(
          makeEvent(candles, lowerHigh.detector, 'market_structure', lowerHigh.bias, i, [
            {
              index: lowerHigh.point1.index,
              price: lowerHigh.point1.price,
              role: 'high',
              confirmedAtIndex: lowerHigh.point1.confirmedAtIndex,
            },
            {
              index: lowerHigh.point2.index,
              price: lowerHigh.point2.price,
              role: 'high',
              confirmedAtIndex: lowerHigh.point2.confirmedAtIndex,
            },
          ]),
        );
      }
    }

    if (addedLows.length > 0) {
      const swings = { highs: windowHighs, lows: windowLows };
      const lowerLow = detectLowerLow(swings);
      if (lowerLow && lowerLow.point2.confirmedAtIndex === i) {
        push(
          makeEvent(candles, lowerLow.detector, 'market_structure', lowerLow.bias, i, [
            {
              index: lowerLow.point1.index,
              price: lowerLow.point1.price,
              role: 'low',
              confirmedAtIndex: lowerLow.point1.confirmedAtIndex,
            },
            {
              index: lowerLow.point2.index,
              price: lowerLow.point2.price,
              role: 'low',
              confirmedAtIndex: lowerLow.point2.confirmedAtIndex,
            },
          ]),
        );
      }
      const higherLow = detectHigherLow(swings);
      if (higherLow && higherLow.point2.confirmedAtIndex === i) {
        push(
          makeEvent(candles, higherLow.detector, 'market_structure', higherLow.bias, i, [
            {
              index: higherLow.point1.index,
              price: higherLow.point1.price,
              role: 'low',
              confirmedAtIndex: higherLow.point1.confirmedAtIndex,
            },
            {
              index: higherLow.point2.index,
              price: higherLow.point2.price,
              role: 'low',
              confirmedAtIndex: higherLow.point2.confirmedAtIndex,
            },
          ]),
        );
      }
    }

    if (
      (addedHighs.length > 0 || addedLows.length > 0) &&
      windowHighs.length >= 2 &&
      windowLows.length >= 2
    ) {
      const linePatterns = [
        detectAscendingTriangle(windowHighs, windowLows),
        detectDescendingTriangle(windowHighs, windowLows),
        detectSymmetricalTriangle(windowHighs, windowLows),
        detectRisingWedge(windowHighs, windowLows),
        detectFallingWedge(windowHighs, windowLows),
      ];
      for (const pattern of linePatterns) {
        if (!pattern) continue;
        push(
          makeEvent(candles, pattern.detector, 'chart_structure', pattern.bias, i, [
            {
              index: pattern.high1.index,
              price: pattern.high1.price,
              role: 'high',
              confirmedAtIndex: pattern.high1.confirmedAtIndex,
            },
            {
              index: pattern.high2.index,
              price: pattern.high2.price,
              role: 'high',
              confirmedAtIndex: pattern.high2.confirmedAtIndex,
            },
            {
              index: pattern.low1.index,
              price: pattern.low1.price,
              role: 'low',
              confirmedAtIndex: pattern.low1.confirmedAtIndex,
            },
            {
              index: pattern.low2.index,
              price: pattern.low2.price,
              role: 'low',
              confirmedAtIndex: pattern.low2.confirmedAtIndex,
            },
          ]),
        );
      }
    }

    if (addedPeaks.length > 0) {
      const match = detectDoubleTop(candles, windowPeaks, i, 15);
      if (match && addedPeaks.some((peak) => peak.index === match.second.index)) {
        push(
          makeEvent(candles, 'double_top', 'chart_structure', 'bearish', i, [
            {
              index: match.first.index,
              price: match.first.price,
              role: 'peak',
              confirmedAtIndex: match.first.confirmedAtIndex,
            },
            {
              index: match.second.index,
              price: match.second.price,
              role: 'peak',
              confirmedAtIndex: match.second.confirmedAtIndex,
            },
          ]),
        );
      }
    }

    if (addedTroughs.length > 0) {
      const match = detectDoubleBottom(candles, windowTroughs, i, 15);
      if (match && addedTroughs.some((trough) => trough.index === match.second.index)) {
        push(
          makeEvent(candles, 'double_bottom', 'chart_structure', 'bullish', i, [
            {
              index: match.first.index,
              price: match.first.price,
              role: 'trough',
              confirmedAtIndex: match.first.confirmedAtIndex,
            },
            {
              index: match.second.index,
              price: match.second.price,
              role: 'trough',
              confirmedAtIndex: match.second.confirmedAtIndex,
            },
          ]),
        );
      }
    }

    const sweepHigh = detectLiquiditySweepHigh(candles, i, swingsNow);
    if (sweepHigh) {
      push(
        makeEvent(candles, sweepHigh.detector, 'market_structure', sweepHigh.bias, i, [
          { index: i, price: candle.close, role: 'candle', confirmedAtIndex: i },
          {
            index: sweepHigh.levelSwing.index,
            price: sweepHigh.levelSwing.price,
            role: 'high',
            confirmedAtIndex: sweepHigh.levelSwing.confirmedAtIndex,
          },
        ], sweepHigh.sweptLevel),
      );
    }
    const sweepLow = detectLiquiditySweepLow(candles, i, swingsNow);
    if (sweepLow) {
      push(
        makeEvent(candles, sweepLow.detector, 'market_structure', sweepLow.bias, i, [
          { index: i, price: candle.close, role: 'candle', confirmedAtIndex: i },
          {
            index: sweepLow.levelSwing.index,
            price: sweepLow.levelSwing.price,
            role: 'low',
            confirmedAtIndex: sweepLow.levelSwing.confirmedAtIndex,
          },
        ], sweepLow.sweptLevel),
      );
    }
  }

  const ordered = [...events.values()].sort(
    (a, b) =>
      a.confirmedAtIndex - b.confirmedAtIndex ||
      a.detector.localeCompare(b.detector) ||
      a.key.localeCompare(b.key),
  );

  return {
    events: ordered,
    swings: { highs, lows },
    provisionalSwings: findProvisionalSwings(candles, swingWindow),
  };
}
