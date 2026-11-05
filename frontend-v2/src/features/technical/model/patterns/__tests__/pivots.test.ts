// model/patterns/__tests__/pivots.test.ts
import { describe, expect, it } from 'vitest';
import { findAlternatingPivots, isPivotHigh, isPivotLow } from '../pivots';
import type { EngineCandle } from '../../doubleTapEngine';

const candle = (high: number, low: number, i: number): EngineCandle => ({
  timestamp: 1_700_000_000_000 + i * 60_000, open: low, high, low, close: (high + low) / 2,
});

// highs: 10, 12, 9, 14, 8, 11  / lows: 5, 6, 4, 7, 3, 5
const series: EngineCandle[] = [
  candle(10, 5, 0), candle(12, 6, 1), candle(9, 4, 2),
  candle(14, 7, 3), candle(8, 3, 4), candle(11, 5, 5),
];

describe('pivot primitives', () => {
  it('detects a fractal high and low with asymmetric windows', () => {
    expect(isPivotHigh(series, 3, 2, 1)).toBe(true);
    expect(isPivotHigh(series, 2, 2, 1)).toBe(false);
    expect(isPivotLow(series, 4, 2, 1)).toBe(true);
  });

  it('returns alternating pivots, keeping the more extreme on a repeat', () => {
    const pivots = findAlternatingPivots(series, 1, 1);
    expect(pivots.map((p) => `${p.kind}:${p.index}`)).toEqual(['high:1', 'low:2', 'high:3', 'low:4']);
  });
});
