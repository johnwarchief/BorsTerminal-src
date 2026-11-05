import { describe, expect, it } from 'vitest';
import { estimatePatternFormation } from '../formation';
import { PATTERN_CONFIG } from '../config';
import type { ChartPattern } from '../types';

const point = (index: number, price: number) => ({ index, price, timestamp: index * 60_000 });
const pattern = (id: string, anchorIndex: number, status: ChartPattern['status'], quality = 60): ChartPattern => ({
  id, kind: 'FLAG_BULL', direction: 'bullish', family: 'continuation',
  anchor: point(anchorIndex, 105), points: [point(anchorIndex - 1, 100), point(anchorIndex, 105)],
  upper: { from: point(anchorIndex, 106), to: point(anchorIndex, 106) },
  lower: { from: point(anchorIndex, 104), to: point(anchorIndex, 104) },
  target: 112, stopLoss: 98, quality, status,
});

describe('formation estimate', () => {
  it('returns no probability under 8 resolved samples', () => {
    const current = pattern('current', 40, 'forming');
    const all = [current, pattern('a', 5, 'confirmed'), pattern('b', 10, 'confirmed')];
    const candles = Array.from({ length: 60 }, (_, i) => ({ timestamp: i * 60_000, open: 100, high: 101, low: 99, close: 100 }));
    const estimate = estimatePatternFormation(current, all, candles, 1, PATTERN_CONFIG);
    expect(estimate?.probability).toBeNull();
    expect(estimate?.resolved).toBeLessThan(8);
  });

  it('returns null for a non-forming pattern', () => {
    const current = pattern('current', 40, 'confirmed');
    expect(estimatePatternFormation(current, [current], [], 1, PATTERN_CONFIG)).toBeNull();
  });
});
