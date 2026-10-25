import { describe, expect, it } from 'vitest';
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
} from '../index';
import type { Candle } from '../types';
import { candle, swing } from './helpers';

const flatCandles = (n: number, price = 100): Candle[] =>
  Array.from({ length: n }, (_, i) => candle(i, price, price, price, price));

describe('ported chart-structure detectors', () => {
  const highs = (p1: number, p2: number, i1 = 10, i2 = 20) => [
    swing(i1, p1, i1 + 3),
    swing(i2, p2, i2 + 3),
  ];
  const lows = (p1: number, p2: number, i1 = 8, i2 = 18) => [
    swing(i1, p1, i1 + 3),
    swing(i2, p2, i2 + 3),
  ];

  it('detects an ascending triangle when highs are flat and lows rise', () => {
    expect(detectAscendingTriangle(highs(100, 100), lows(90, 94))?.detector).toBe(
      'ascending_triangle',
    );
  });

  it('rejects an ascending triangle with rising highs', () => {
    expect(detectAscendingTriangle(highs(100, 101), lows(90, 94))).toBeNull();
  });

  it('rejects an ascending triangle when lows are nearly flat', () => {
    expect(detectAscendingTriangle(highs(100, 100), lows(90, 90.02))).toBeNull();
  });

  it('detects a descending triangle', () => {
    const result = detectDescendingTriangle(highs(100, 99), lows(90, 90.1));
    expect(result?.detector).toBe('descending_triangle');
    expect(result?.bias).toBe('bearish');
  });

  it('rejects a descending triangle when the high line is not above the low line', () => {
    expect(detectDescendingTriangle(highs(100, 89), lows(90, 90.1))).toBeNull();
  });

  it('detects a symmetrical triangle', () => {
    expect(detectSymmetricalTriangle(highs(100, 99), lows(90, 94))?.detector).toBe(
      'symmetrical_triangle',
    );
  });

  it('rejects a symmetrical triangle when both lines fall', () => {
    expect(detectSymmetricalTriangle(highs(100, 99), lows(90, 89))).toBeNull();
  });

  it('detects a rising wedge when the lower line rises faster', () => {
    expect(detectRisingWedge(highs(100, 101), lows(90, 94))?.detector).toBe('rising_wedge');
  });

  it('detects a falling wedge when the upper line falls faster', () => {
    expect(detectFallingWedge(highs(100, 95), lows(90, 89.2))?.detector).toBe('falling_wedge');
  });

  it('rejects a wedge when both lines have the same slope', () => {
    expect(detectFallingWedge(highs(100, 90), lows(90, 81))).toBeNull();
    expect(detectRisingWedge(highs(100, 110), lows(90, 99))).toBeNull();
  });

  it('rejects a rising wedge when both lines fall', () => {
    expect(detectRisingWedge(highs(100, 99), lows(90, 89))).toBeNull();
  });

  it('compares only the last two confirmed swings', () => {
    const older = swing(2, 500, 5);
    const recentHighs = [older, ...highs(100, 100)];
    const recentLows = [swing(1, 400, 4), ...lows(90, 94)];
    expect(detectAscendingTriangle(recentHighs, recentLows)).not.toBeNull();
  });
});

describe('ported double top/bottom matching', () => {
  it('accepts a double top at the 4% price-difference boundary', () => {
    const candles = flatCandles(30);
    candles[15] = candle(15, 96, 100, 95, 96);
    const peaks = [swing(10, 100, 15), swing(20, 104, 25)];
    expect(detectDoubleTop(candles, peaks, 25, 15)?.detector).toBe('double_top');
  });

  it('rejects a price difference above 4%', () => {
    const candles = flatCandles(30);
    candles[15] = candle(15, 96, 100, 95, 96);
    const peaks = [swing(10, 100, 15), swing(20, 110, 25)];
    expect(detectDoubleTop(candles, peaks, 25, 15)).toBeNull();
  });

  it('requires a pullback strictly greater than 1%', () => {
    const onePercent = flatCandles(30);
    onePercent[15] = candle(15, 100, 100, 99, 100);
    expect(
      detectDoubleTop(onePercent, [swing(10, 100, 15), swing(20, 100, 25)], 25, 15),
    ).toBeNull();

    const belowOne = flatCandles(30);
    belowOne[15] = candle(15, 100, 100, 99.5, 100);
    expect(
      detectDoubleTop(belowOne, [swing(10, 100, 15), swing(20, 100, 25)], 25, 15),
    ).toBeNull();
  });

  it('requires at least 5 bars between peaks', () => {
    const candles = flatCandles(30);
    candles[18] = candle(18, 96, 100, 95, 96);
    const peaks = [swing(16, 100, 21), swing(20, 100, 25)];
    expect(detectDoubleTop(candles, peaks, 25, 15)).toBeNull();
  });

  it('applies the recency window from the pivot confirmation, inclusively', () => {
    const candles = flatCandles(45);
    candles[15] = candle(15, 96, 100, 95, 96);
    const peaks = [swing(10, 100, 15), swing(20, 100, 25)];
    expect(detectDoubleTop(candles, peaks, 40, 15)?.detector).toBe('double_top');
    expect(detectDoubleTop(candles, peaks, 41, 15)).toBeNull();
  });

  it('accepts a double bottom only with a bounce above 1%', () => {
    const bounce = flatCandles(30);
    bounce[10] = candle(10, 90, 90, 90, 90);
    bounce[20] = candle(20, 88, 88, 88, 88);
    bounce[15] = candle(15, 104, 105, 100, 104);
    expect(
      detectDoubleBottom(bounce, [swing(10, 90, 15), swing(20, 88, 25)], 25, 15)?.detector,
    ).toBe('double_bottom');

    const weak = flatCandles(30, 89);
    weak[10] = candle(10, 90, 90, 90, 90);
    weak[20] = candle(20, 90, 90, 90, 90);
    weak[15] = candle(15, 90, 90.5, 89.5, 90);
    expect(
      detectDoubleBottom(weak, [swing(10, 90, 15), swing(20, 90, 25)], 25, 15),
    ).toBeNull();
  });

  it('rejects a double bottom when troughs differ by more than 4%', () => {
    const candles = flatCandles(30);
    candles[10] = candle(10, 90, 90, 90, 90);
    candles[20] = candle(20, 95, 95, 95, 95);
    candles[15] = candle(15, 104, 105, 100, 104);
    expect(
      detectDoubleBottom(candles, [swing(10, 90, 15), swing(20, 95, 25)], 25, 15),
    ).toBeNull();
  });
});

describe('ported market-structure detectors', () => {
  const structure = (highPrices: number[], lowPrices: number[]) => ({
    highs: highPrices.map((p, i) => swing(10 + i * 10, p, 13 + i * 10)),
    lows: lowPrices.map((p, i) => swing(8 + i * 10, p, 11 + i * 10)),
  });

  it('classifies higher high and lower high', () => {
    expect(detectHigherHigh(structure([100, 101], []) )?.detector).toBe('higher_high');
    expect(detectLowerHigh(structure([101, 100], []) )?.detector).toBe('lower_high');
    expect(detectHigherHigh(structure([100, 100], []))).toBeNull();
    expect(detectLowerHigh(structure([100, 100], []))).toBeNull();
  });

  it('classifies higher low and lower low', () => {
    expect(detectHigherLow(structure([], [90, 91]))?.detector).toBe('higher_low');
    expect(detectLowerLow(structure([], [91, 90]))?.detector).toBe('lower_low');
    expect(detectHigherLow(structure([], [90, 90]))).toBeNull();
    expect(detectLowerLow(structure([], [90, 90]))).toBeNull();
  });

  it('emits bullish BOS at the close-through bar, not the pivot confirmation', () => {
    const candles = flatCandles(30);
    candles[20] = candle(20, 100, 101.5, 99.5, 101);
    const swings = { highs: [swing(10, 100, 13)], lows: [] };
    const event = detectBosBullish(candles, 20, swings);
    expect(event).toMatchObject({
      detector: 'bos_bullish',
      brokenLevel: 100,
      confirmedAtIndex: 20,
      barIndex: 20,
    });
    expect(event?.levelSwing.index).toBe(10);
  });

  it('applies an explicit 0.5% close-penetration threshold', () => {
    const candles = flatCandles(30);
    candles[20] = candle(20, 100, 100.6, 99.5, 100.5);
    const swings = { highs: [swing(10, 100, 13)], lows: [] };
    expect(detectBosBullish(candles, 20, swings, 0.005)).toBeNull();

    candles[20] = candle(20, 100, 100.7, 99.5, 100.6);
    expect(detectBosBullish(candles, 20, swings, 0.005)?.detector).toBe('bos_bullish');
  });

  it('mirrors the bearish threshold and close-through bar', () => {
    const candles = flatCandles(30);
    candles[20] = candle(20, 100, 100.5, 99.5, 99.5);
    const swings = { highs: [], lows: [swing(10, 100, 13)] };
    expect(detectBosBearish(candles, 20, swings, 0.005)).toBeNull();

    candles[20] = candle(20, 100, 100.5, 99.3, 99.4);
    expect(detectBosBearish(candles, 20, swings, 0.005)).toMatchObject({
      detector: 'bos_bearish',
      confirmedAtIndex: 20,
      brokenLevel: 100,
    });
  });

  it('does not use a level confirmed on the break bar itself', () => {
    const candles = flatCandles(30);
    candles[20] = candle(20, 100, 101.5, 99.5, 101);
    const sameBar = { highs: [swing(10, 100, 20)], lows: [] };
    expect(detectBosBullish(candles, 20, sameBar)).toBeNull();

    const knownBefore = { highs: [swing(10, 100, 19)], lows: [] };
    expect(detectBosBullish(candles, 20, knownBefore)?.detector).toBe('bos_bullish');
  });

  it('requires the previous close to be at or below the broken high', () => {
    const candles = flatCandles(30);
    candles[19] = candle(19, 101, 101.5, 100.5, 101);
    candles[20] = candle(20, 101, 102.5, 100.5, 102);
    const swings = { highs: [swing(10, 100, 13)], lows: [] };
    expect(detectBosBullish(candles, 20, swings)).toBeNull();
  });

  it('sweeps the latest confirmed swing high, not the one before it', () => {
    const candles = flatCandles(40);
    candles[30] = candle(30, 108, 111, 107, 109);
    const swings = { highs: [swing(10, 100, 13), swing(20, 110, 23)], lows: [] };
    const event = detectLiquiditySweepHigh(candles, 30, swings);
    expect(event).toMatchObject({ detector: 'liquidity_sweep_high', sweptLevel: 110 });
  });

  it('requires a close back inside the level for a high sweep', () => {
    const candles = flatCandles(40);
    candles[30] = candle(30, 108, 111, 107, 110.5);
    const swings = { highs: [swing(10, 100, 13), swing(20, 110, 23)], lows: [] };
    expect(detectLiquiditySweepHigh(candles, 30, swings)).toBeNull();
  });

  it('requires the high to pierce the level, not touch it', () => {
    const candles = flatCandles(40);
    candles[30] = candle(30, 108, 110, 107, 109);
    const swings = { highs: [swing(10, 100, 13), swing(20, 110, 23)], lows: [] };
    expect(detectLiquiditySweepHigh(candles, 30, swings)).toBeNull();
  });

  it('ignores a swing that is not confirmed yet', () => {
    const candles = flatCandles(40);
    candles[30] = candle(30, 108, 111, 107, 109);
    const swings = { highs: [swing(10, 100, 13), swing(20, 110, 31)], lows: [] };
    expect(detectLiquiditySweepHigh(candles, 30, swings)).toBeNull();
  });

  it('mirrors the low sweep', () => {
    const candles = flatCandles(40);
    candles[30] = candle(30, 90, 92, 87, 89);
    const swings = { highs: [], lows: [swing(10, 90, 13), swing(20, 88, 23)] };
    expect(detectLiquiditySweepLow(candles, 30, swings)).toMatchObject({
      detector: 'liquidity_sweep_low',
      sweptLevel: 88,
    });

    candles[30] = candle(30, 90, 92, 87, 87.5);
    expect(detectLiquiditySweepLow(candles, 30, swings)).toBeNull();
  });
});
