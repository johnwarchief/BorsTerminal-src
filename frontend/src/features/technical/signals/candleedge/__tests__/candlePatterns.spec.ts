import { describe, expect, it } from 'vitest';
import {
  isBearishEngulfing,
  isBullishEngulfing,
  isDoji,
  isHammer,
  isShootingStar,
} from '../index';
import { bodyCandle, candle } from './helpers';

describe('ported candlestick detectors (CandleEdge formulas)', () => {
  describe('isDoji', () => {
    it('accepts body <= 12% of range (boundary is inclusive)', () => {
      expect(isDoji(bodyCandle(12, 100))).toBe(true);
    });

    it('rejects body above 12% of range', () => {
      expect(isDoji(bodyCandle(12.5, 100))).toBe(false);
    });

    it('rejects a zero-range bar instead of treating the fallback range as indecision', () => {
      const flat = candle(0, 100, 100, 100, 100);
      expect(isDoji(flat)).toBe(false);
    });
  });

  describe('engulfing', () => {
    const bearish = candle(0, 60, 61, 49, 50);

    it('bullish engulfing accepts exact open=prev.close and close=prev.open', () => {
      const current = candle(1, 50, 61, 49, 60);
      expect(isBullishEngulfing([bearish, current], 1)).toBe(true);
    });

    it('bullish engulfing rejects a body that does not cover the previous close', () => {
      const current = candle(1, 51, 61, 49, 60);
      expect(isBullishEngulfing([bearish, current], 1)).toBe(false);
    });

    it('bullish engulfing rejects when the previous candle is not bearish', () => {
      const previous = candle(0, 50, 61, 49, 60);
      const current = candle(1, 49, 61, 48, 60);
      expect(isBullishEngulfing([previous, current], 1)).toBe(false);
    });

    it('engulfing needs a previous candle', () => {
      expect(isBullishEngulfing([bearish], 0)).toBe(false);
      expect(isBearishEngulfing([bearish], 0)).toBe(false);
    });

    it('bearish engulfing accepts the mirrored boundary', () => {
      const previous = candle(0, 50, 61, 49, 60);
      const current = candle(1, 60, 61, 49, 50);
      expect(isBearishEngulfing([previous, current], 1)).toBe(true);
    });

    it('bearish engulfing rejects a short body', () => {
      const previous = candle(0, 50, 61, 49, 60);
      const current = candle(1, 59, 61, 49, 50);
      expect(isBearishEngulfing([previous, current], 1)).toBe(false);
    });
  });

  describe('hammer', () => {
    const downtrend = Array.from({ length: 21 }, (_, i) =>
      candle(i, 120 - i, 121 - i, 119 - i, 120 - i),
    );

    it('accepts a hammer after a 20-bar downtrend', () => {
      const last = candle(21, 100, 102.9, 95.9, 102);
      expect(isHammer([...downtrend, last], 21)).toBe(true);
    });

    it('rejects lower wick equal to twice the body (strict inequality)', () => {
      const last = candle(21, 100, 102.9, 96, 102);
      expect(isHammer([...downtrend, last], 21)).toBe(false);
    });

    it('rejects the shape without a downtrend', () => {
      const flat = Array.from({ length: 21 }, (_, i) => candle(i, 95, 96, 94, 95));
      const last = candle(21, 100, 102.9, 95.9, 102);
      expect(isHammer([...flat, last], 21)).toBe(false);
    });

    it('needs 20 bars of trend context', () => {
      const last = candle(0, 100, 102.9, 95.9, 102);
      expect(isHammer([last], 0)).toBe(false);
    });
  });

  describe('shooting star', () => {
    const uptrend = Array.from({ length: 21 }, (_, i) =>
      candle(i, 80 + i, 81 + i, 79 + i, 80 + i),
    );

    it('accepts a shooting star after a 20-bar uptrend', () => {
      const last = candle(21, 102, 106.1, 99.9, 100);
      expect(isShootingStar([...uptrend, last], 21)).toBe(true);
    });

    it('rejects upper wick equal to twice the body (strict inequality)', () => {
      const last = candle(21, 102, 106, 99.9, 100);
      expect(isShootingStar([...uptrend, last], 21)).toBe(false);
    });

    it('rejects the shape without an uptrend', () => {
      const down = Array.from({ length: 21 }, (_, i) => candle(i, 120, 121, 119, 120));
      const last = candle(21, 102, 106.1, 99.9, 100);
      expect(isShootingStar([...down, last], 21)).toBe(false);
    });
  });
});
