import { describe, expect, it } from 'vitest';
import { CandleEdgeInputError, assertValidCandles, scanPatterns } from '../index';
import { candle } from './helpers';

describe('candle input validation', () => {
  it('accepts an empty series (scan yields no events)', () => {
    expect(() => assertValidCandles([])).not.toThrow();
    expect(scanPatterns([]).events).toEqual([]);
  });

  it('accepts a well-formed series', () => {
    const series = [candle(0, 10, 12, 9, 11), candle(1, 11, 13, 10, 12)];
    expect(() => assertValidCandles(series)).not.toThrow();
  });

  it('rejects non-finite OHLC values', () => {
    const series = [candle(0, 10, Number.NaN, 9, 11)];
    expect(() => assertValidCandles(series)).toThrow(CandleEdgeInputError);
    try {
      assertValidCandles(series);
    } catch (error) {
      expect((error as CandleEdgeInputError).index).toBe(0);
      expect((error as CandleEdgeInputError).reason).toBe('ohlc-not-finite');
    }
  });

  it('rejects high below max(open, close)', () => {
    const series = [candle(0, 10, 10.5, 9, 11)];
    expect(() => assertValidCandles(series)).toThrow(/high-below-body/);
  });

  it('rejects low above min(open, close)', () => {
    const series = [candle(0, 10, 12, 10.5, 9)];
    expect(() => assertValidCandles(series)).toThrow(/low-above-body/);
  });

  it('rejects non-positive prices', () => {
    const series = [candle(0, 0, 1, 0, 0.5)];
    expect(() => assertValidCandles(series)).toThrow(/price-not-positive/);
  });

  it('rejects unordered time', () => {
    const series = [candle(2, 10, 12, 9, 11), candle(1, 11, 13, 10, 12)];
    expect(() => assertValidCandles(series)).toThrow(/time-not-increasing/);
  });
});
