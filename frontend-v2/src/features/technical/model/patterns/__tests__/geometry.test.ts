// model/patterns/__tests__/geometry.test.ts
import { describe, expect, it } from 'vitest';
import { emitPattern, lineSlope, lineValue } from '../geometry';
import { PATTERN_CONFIG } from '../config';
import type { EngineCandle } from '../../doubleTapEngine';

const candle = (high: number, low: number, close: number, i: number): EngineCandle => ({
  timestamp: 1_700_000_000_000 + i * 60_000, open: low, high, low, close,
});
const flat: EngineCandle[] = Array.from({ length: 12 }, (_, i) => candle(110, 100, 105, i));
const point = (index: number, price: number) => ({ index, price, timestamp: index * 60_000 });

describe('geometry', () => {
  it('interpolates a boundary line and reports its slope', () => {
    const line = { from: point(2, 100), to: point(6, 110) };
    expect(lineValue(line, 4)).toBe(105);
    expect(lineSlope(line)).toBe(2.5);
  });

  it('returns null for an expired forming pattern', () => {
    const spec = {
      kind: 'RECTANGLE' as const, direction: 'neutral' as const, family: 'continuation' as const,
      points: [point(1, 100), point(2, 110), point(3, 100), point(4, 110)],
      upper: { from: point(2, 110), to: point(4, 110) },
      lower: { from: point(1, 100), to: point(3, 100) },
      target: 120, stopLoss: 95, quality: 70, maxBars: 3,
    };
    // آخرین پیوت ۲۰ کندل عقب‌تر از انتهای داده است ⇒ منقضی، نباید الگو بسازد.
    const emitted = emitPattern(spec, flat, { ...PATTERN_CONFIG, rectangle: { ...PATTERN_CONFIG.rectangle, maxBars: 3 } });
    expect(emitted).toBeNull();
  });
});
