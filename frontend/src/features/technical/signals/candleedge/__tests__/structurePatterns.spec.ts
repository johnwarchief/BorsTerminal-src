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

  it('applies the recency window inclusively', () => {
    const candles = flatCandles(40);
    candles[15] = candle(15, 96, 100, 95, 96);
    const peaks = [swing(10, 100, 15), swing(20, 100, 25)];
    expect(detectDoubleTop(candles, peaks, 35, 15)?.detector).toBe('double_top');
    expect(detectDoubleTop(candles, peaks, 36, 15)).toBeNull();
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

  it('emits bullish BOS at the confirmation bar of the new swing', () => {
    const swings = { highs: [swing(10, 100, 13), swing(20, 101, 23)], lows: [] };
    const event = detectBosBullish(swings, 23);
    expect(event).toMatchObject({
      detector: 'bos_bullish',
      brokenLevel: 100,
      confirmedAtIndex: 23,
    });
    expect(event?.newSwing.index).toBe(20);
  });

  it('rejects bearish BOS exactly at the 0.5% threshold', () => {
    const swings = { highs: [], lows: [swing(10, 100, 13), swing(20, 99.5, 23)] };
    expect(detectBosBearish(swings, 23)).toBeNull();
  });

  it('emits bearish BOS below the 0.5% threshold', () => {
    const swings = { highs: [], lows: [swing(10, 100, 13), swing(20, 99.4, 23)] };
    expect(detectBosBearish(swings, 23)?.detector).toBe('bos_bearish');
  });

  it('does not evaluate BOS before the new swing is confirmed', () => {
    const swings = { highs: [swing(10, 100, 13), swing(20, 101, 23)], lows: [] };
    expect(detectBosBullish(swings, 22)).toBeNull();
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
