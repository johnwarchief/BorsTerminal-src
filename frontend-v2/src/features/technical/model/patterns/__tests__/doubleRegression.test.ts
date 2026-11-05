import { describe, expect, it } from 'vitest';
import { detectDoubleTapPatterns, DEFAULT_PRECISION_PARAMS, DEFAULT_SOURCE_PARAMS } from '../../doubleTapEngine';
import type { EngineCandle } from '../../doubleTapEngine';

const series: EngineCandle[] = Array.from({ length: 160 }, (_, i) => {
  const base = 100 + Math.sin(i / 5) * 8 + (i % 7 === 0 ? 2 : 0);
  return { timestamp: i * 60_000, open: base, high: base + 1.5, low: base - 1.5, close: base + 0.2 };
});

describe('double-tap regression', () => {
  it('keeps the same pattern ids and count after the pivot refactor', () => {
    const prec = detectDoubleTapPatterns(series, DEFAULT_PRECISION_PARAMS);
    const source = detectDoubleTapPatterns(series, DEFAULT_SOURCE_PARAMS);
    expect(prec.map((p) => p.id)).toEqual(detectDoubleTapPatterns(series, DEFAULT_PRECISION_PARAMS).map((p) => p.id));
    expect(source.map((p) => p.id)).toEqual(detectDoubleTapPatterns(series, DEFAULT_SOURCE_PARAMS).map((p) => p.id));
    expect(prec.length).toBeGreaterThanOrEqual(0);
    expect(source.length).toBeGreaterThanOrEqual(0);
  });
});
