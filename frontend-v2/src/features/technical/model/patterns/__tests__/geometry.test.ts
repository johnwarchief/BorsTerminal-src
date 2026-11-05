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
/** atr=1 در این تست‌ها؛ بافر همان ۰٫۵×ATR پیکربندی است. */
const BUFFER = PATTERN_CONFIG.invalidationBufferAtr;
const neutralSpec = () => ({
  kind: 'RECTANGLE' as const, direction: 'neutral' as const, family: 'continuation' as const,
  points: [point(1, 100), point(2, 110), point(3, 100), point(4, 110)],
  upper: { from: point(2, 110), to: point(4, 110) },
  lower: { from: point(1, 100), to: point(3, 100) },
  target: 120, stopLoss: 95, quality: 70, maxBars: 8, invalidationBuffer: BUFFER,
});
/** همان هندسه، ولی جهت‌دار: برای سنجش بافرِ ابطال لازم است. */
const bullishSpec = () => ({
  kind: 'FLAG_BULL' as const, direction: 'bullish' as const, family: 'continuation' as const,
  points: [point(1, 100), point(2, 110), point(3, 100), point(4, 110)],
  upper: { from: point(2, 110), to: point(4, 110) },
  lower: { from: point(1, 100), to: point(3, 100) },
  target: 120, stopLoss: 95, quality: 70, maxBars: 8, invalidationBuffer: BUFFER,
});

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
      target: 120, stopLoss: 95, quality: 70, maxBars: 3, invalidationBuffer: BUFFER,
    };
    // آخرین پیوت ۲۰ کندل عقب‌تر از انتهای داده است ⇒ منقضی، نباید الگو بسازد.
    const emitted = emitPattern(spec, flat, { ...PATTERN_CONFIG, rectangle: { ...PATTERN_CONFIG.rectangle, maxBars: 3 } });
    expect(emitted).toBeNull();
  });

  it('confirms a neutral pattern on a close above the upper line', () => {
    const candles = flat.map((c, i) => (i === 6 ? { ...c, close: 112 } : c));
    const emitted = emitPattern(neutralSpec(), candles, PATTERN_CONFIG);
    expect(emitted).not.toBeNull();
    expect(emitted?.status).toBe('confirmed');
    expect(emitted?.breakoutIndex).toBe(6);
    expect(emitted?.direction).toBe('neutral');
  });

  it('confirms a neutral pattern on a close below the lower line', () => {
    const candles = flat.map((c, i) => (i === 7 ? { ...c, close: 98 } : c));
    const emitted = emitPattern(neutralSpec(), candles, PATTERN_CONFIG);
    expect(emitted).not.toBeNull();
    expect(emitted?.status).toBe('confirmed');
    expect(emitted?.breakoutIndex).toBe(7);
    expect(emitted?.direction).toBe('neutral');
  });

  it('does not invalidate a directional pattern on a close only 0.2·ATR beyond the boundary', () => {
    // atr=1 و بافر ۰٫۵×ATR: بستهٔ ۹۹٫۸ (۰٫۲ زیر مرز پایین) ابطال نیست.
    const candles = flat.map((c, i) => (i === 6 ? { ...c, close: 99.8 } : c));
    const emitted = emitPattern(bullishSpec(), candles, PATTERN_CONFIG);
    expect(emitted).not.toBeNull();
    expect(emitted?.status).toBe('forming');
    expect(emitted?.breakoutIndex).toBeUndefined();
  });

  it('invalidates a directional pattern on a close 0.6·ATR beyond the boundary', () => {
    // همان atr=1: بستهٔ ۹۹٫۴ (۰٫۶ زیر مرز) از بافر ۰٫۵ عبور می‌کند ⇒ باطل.
    const candles = flat.map((c, i) => (i === 6 ? { ...c, close: 99.4 } : c));
    const emitted = emitPattern(bullishSpec(), candles, PATTERN_CONFIG);
    expect(emitted).not.toBeNull();
    expect(emitted?.status).toBe('invalidated');
  });

  it('reads the buffer from the spec so every detector passes its own invalidationBuffer', () => {
    // بستهٔ ۹۹٫۶ یعنی ۰٫۴ بیرونِ مرز پایین: با بافر ۰٫۵ هنوز در حال تشکیل، با ۰٫۲ باطل.
    const candles = flat.map((c, i) => (i === 6 ? { ...c, close: 99.6 } : c));
    expect(emitPattern({ ...bullishSpec(), invalidationBuffer: 0.5 }, candles, PATTERN_CONFIG)?.status)
      .toBe('forming');
    expect(emitPattern({ ...bullishSpec(), invalidationBuffer: 0.2 }, candles, PATTERN_CONFIG)?.status)
      .toBe('invalidated');
  });
});
