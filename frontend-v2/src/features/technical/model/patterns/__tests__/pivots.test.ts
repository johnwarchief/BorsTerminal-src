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
    expect(isPivotHigh(series, 0, 2, 1)).toBe(false); // بریدگی چپ: پنجره از صفر شروع می‌شود و high[1]=12 > 10
    expect(isPivotLow(series, 3, 2, 1)).toBe(false); // low[3]=7 و low[2]=4 کوچک‌تر است
  });

  it('returns alternating pivots, keeping the more extreme on a repeat', () => {
    const pivots = findAlternatingPivots(series, 1, 1);
    expect(pivots.map((p) => `${p.kind}:${p.index}`)).toEqual(['high:1', 'low:2', 'high:3', 'low:4']);
  });

  it('keeps only the more extreme when raw pivots repeat the same high kind', () => {
    // highs: 10, 14, 11, 15, 9 و lows صعودی تا هیچ دره‌ای میان درها نباشد.
    // اگر مقایسه‌گر برعکس شود یا شاخهٔ dedup حذف شود، این تست باید شکست بخورد.
    const repeatedHighs: EngineCandle[] = [
      candle(10, 5, 0), candle(14, 6, 1), candle(11, 7, 2), candle(15, 8, 3), candle(9, 5, 4),
    ];
    expect(findAlternatingPivots(repeatedHighs, 1, 1).map((p) => `${p.kind}:${p.index}`)).toEqual(['high:3']);
  });

  it('keeps only the more extreme when raw pivots repeat the same low kind', () => {
    // lows: 6, 2, 5, 1, 7 و highs به‌شکل V تا هیچ قلهٔ میانجی‌ای ساخته نشود.
    // اگر مقایسه‌گر برعکس شود یا شاخهٔ dedup حذف شود، این تست باید شکست بخورد.
    const repeatedLows: EngineCandle[] = [
      candle(10, 6, 0), candle(9, 2, 1), candle(8, 5, 2), candle(9, 1, 3), candle(10, 7, 4),
    ];
    expect(findAlternatingPivots(repeatedLows, 1, 1).map((p) => `${p.kind}:${p.index}`)).toEqual(['low:3']);
  });
});
