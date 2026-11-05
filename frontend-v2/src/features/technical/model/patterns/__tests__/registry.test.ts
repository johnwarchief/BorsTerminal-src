import { afterEach, describe, expect, it, vi } from 'vitest';
import { detectAllPatterns, selectFeaturedPatterns, fromDoubleTap } from '../registry';
import { PATTERN_CONFIG } from '../config';
import type { ChartPattern } from '../types';
import type { DoubleTapPattern } from '../../types';
import { detectDoubleTapPatterns, DEFAULT_PRECISION_PARAMS } from '../../doubleTapEngine';
import type { EngineCandle } from '../../doubleTapEngine';

/**
 * R-PAT-6: فقط تست هم‌پوشانی دتکتورها را با خروجی مصنوعی جایگزین می‌کند؛
 * تا وقتی synthetic خالی است، همان دتکتورهای واقعی اجرا می‌شوند.
 */
const detectors = vi.hoisted(() => ({
  synthetic: null as null | { continuation: ChartPattern[]; reversal: ChartPattern[] },
}));

vi.mock('../detectContinuation', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../detectContinuation')>();
  return {
    detectContinuation: (...args: Parameters<typeof actual.detectContinuation>) =>
      detectors.synthetic ? detectors.synthetic.continuation : actual.detectContinuation(...args),
  };
});

vi.mock('../detectReversal', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../detectReversal')>();
  return {
    detectReversal: (...args: Parameters<typeof actual.detectReversal>) =>
      detectors.synthetic ? detectors.synthetic.reversal : actual.detectReversal(...args),
  };
});

afterEach(() => {
  detectors.synthetic = null;
});

const series: EngineCandle[] = Array.from({ length: 120 }, (_, i) => {
  const base = 100 + Math.sin(i / 6) * 6;
  return { timestamp: i * 60_000, open: base, high: base + 1.2, low: base - 1.2, close: base + 0.3 };
});

/** سری یکنوا: پیوتی ندارد، پس دوقلوی واقعی روی آن ساخته نمی‌شود. */
const monotonic: EngineCandle[] = Array.from({ length: 40 }, (_, i) => {
  const base = 100 + i * 0.1;
  return { timestamp: i * 60_000, open: base, high: base + 0.5, low: base - 0.5, close: base + 0.2 };
});

const point = (index: number, price: number) => ({ index, price, timestamp: index * 60_000 });

const shaped = (id: string, anchorIndex: number, family: ChartPattern['family']): ChartPattern => ({
  id,
  kind: family === 'reversal' ? 'HEAD_SHOULDERS' : 'FLAG_BULL',
  direction: 'bullish',
  family,
  anchor: point(anchorIndex, 100),
  points: [point(anchorIndex, 100)],
  upper: { from: point(anchorIndex, 101), to: point(anchorIndex, 101) },
  lower: { from: point(anchorIndex, 99), to: point(anchorIndex, 99) },
  target: 110,
  stopLoss: 95,
  quality: 60,
  status: 'confirmed',
});

describe('pattern registry', () => {
  it('merges new patterns with the existing double taps and keeps doubles intact', () => {
    const all = detectAllPatterns(series, PATTERN_CONFIG);
    const doubles = detectDoubleTapPatterns(series, DEFAULT_PRECISION_PARAMS).map(fromDoubleTap);
    expect(doubles.every((d) => d.kind === 'DOUBLE_TOP' || d.kind === 'DOUBLE_BOTTOM')).toBe(true);
    expect(all.length).toBeGreaterThanOrEqual(doubles.length);
    expect(new Set(all.map((p) => p.id)).size).toBe(all.length);
  });

  it('features at most six shapes', () => {
    const all = detectAllPatterns(series, PATTERN_CONFIG);
    expect(selectFeaturedPatterns(all, 6).length).toBeLessThanOrEqual(6);
  });

  it('keeps the double-tap breakout index when adapting', () => {
    const double: DoubleTapPattern = {
      id: 'double-top-10-20',
      type: 'DOUBLE_TOP',
      peak1: point(10, 110),
      neckline: point(15, 100),
      peak2: point(20, 111),
      retest: point(24, 100),
      breakoutIndex: 26,
      breakoutTs: 26 * 60_000,
      target1: 90,
      target2: 85,
      stopLoss: 112,
      score: 70,
      quality: 70,
      height: 10,
      status: 'active',
      profile: 'precision',
    };
    const adapted = fromDoubleTap(double);
    expect(adapted.breakoutIndex).toBe(26);
    expect(adapted.kind).toBe('DOUBLE_TOP');
    expect(adapted.family).toBe('reversal');
  });

  it('drops a continuation anchor sitting within three bars of a reversal anchor', () => {
    detectors.synthetic = {
      continuation: [shaped('cont-near', 10, 'continuation'), shaped('cont-far', 30, 'continuation')],
      reversal: [shaped('rev', 12, 'reversal')],
    };
    const all = detectAllPatterns(monotonic, PATTERN_CONFIG);
    expect(all.some((p) => p.id === 'rev')).toBe(true);
    expect(all.some((p) => p.id === 'cont-near')).toBe(false);
    expect(all.some((p) => p.id === 'cont-far')).toBe(true);
  });
});
