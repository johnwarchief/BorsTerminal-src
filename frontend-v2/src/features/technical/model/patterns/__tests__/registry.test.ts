import { afterEach, describe, expect, it, vi } from 'vitest';
import { detectAllPatterns, selectFeaturedPatterns, fromDoubleTap } from '../registry';
import { PATTERN_CONFIG } from '../config';
import type { ChartPattern } from '../types';
import type { DoubleTapPattern } from '../../types';
import { detectDoubleTapPatterns, DEFAULT_PRECISION_PARAMS } from '../../doubleTapEngine';
import type { EngineCandle } from '../../doubleTapEngine';
import { outcomeOf } from '../outcome';

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

const bars = (closes: number[]): EngineCandle[] => closes.map((close, i) => ({
  timestamp: i * 60_000, open: close, high: close + 0.5, low: close - 0.5, close,
}));

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

const doubleTap = (over: Partial<DoubleTapPattern> = {}): DoubleTapPattern => ({
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
  ...over,
});

const doubleBottom = (over: Partial<DoubleTapPattern> = {}): DoubleTapPattern => doubleTap({
  id: 'double-bottom-10-20',
  type: 'DOUBLE_BOTTOM',
  peak1: point(10, 90),
  neckline: point(15, 100),
  peak2: point(20, 91),
  retest: point(24, 100),
  target1: 110,
  target2: 115,
  stopLoss: 89,
  ...over,
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
    const adapted = fromDoubleTap(doubleTap());
    expect(adapted.breakoutIndex).toBe(26);
    expect(adapted.kind).toBe('DOUBLE_TOP');
    expect(adapted.family).toBe('reversal');
  });

  it('maps double-tap statuses: active → confirmed and invalidated → invalidated', () => {
    expect(fromDoubleTap(doubleTap({ status: 'active' })).status).toBe('confirmed');
    expect(fromDoubleTap(doubleTap({ status: 'invalidated' })).status).toBe('invalidated');
  });

  it('orders double-bottom boundaries as neckline above trough (upper > lower)', () => {
    const adapted = fromDoubleTap(doubleBottom());
    expect(adapted.direction).toBe('bullish');
    expect(adapted.upper.from.price).toBe(100); // خط گردن
    // مرزِ پایین = min(درهٔ ۹۰، درهٔ ۹۱): هر دو دره درونِ الگو می‌مانند.
    expect(adapted.lower.from.price).toBe(90);
    expect(adapted.upper.from.price).toBeGreaterThan(adapted.lower.from.price);
  });

  it('spans double-tap boundaries from peak1 to the anchor instead of a zero-length point', () => {
    const top = fromDoubleTap(doubleTap());
    // پیش از رفع، from === to بود و اورلی خطِ صفرطول را دور می‌زد ⇒ هیچ مرزی رسم نمی‌شد.
    expect(top.upper.from.index).toBe(10);
    expect(top.upper.to.index).toBe(24);
    expect(top.lower.from.index).toBe(10);
    expect(top.lower.to.index).toBe(24);
    expect(top.upper.from.index).toBeLessThan(top.upper.to.index);
    expect(top.lower.from.index).toBeLessThan(top.lower.to.index);
    // R-PAT-21: سقف = سطح قله‌ها، کف = خط گردن.
    expect(top.upper.from.price).toBe(111);
    expect(top.lower.from.price).toBe(100);
    expect(top.upper.from.price).toBeGreaterThan(top.lower.from.price);

    const bottom = fromDoubleTap(doubleBottom());
    expect(bottom.upper.from.index).toBeLessThan(bottom.upper.to.index);
    expect(bottom.lower.from.index).toBeLessThan(bottom.lower.to.index);
    // R-PAT-21: در دوقلوی کف، خط گردن بالا و کفِ هر دو دره پایین‌اند.
    expect(bottom.upper.from.price).toBe(100);
    expect(bottom.lower.from.price).toBe(90);
    expect(bottom.upper.from.price).toBeGreaterThan(bottom.lower.from.price);
  });

  it('spans both boundaries even when the double has no retest', () => {
    const top = fromDoubleTap(doubleTap({ retest: undefined }));
    expect(top.anchor.index).toBe(20);
    expect(top.upper.from.index).toBe(10);
    expect(top.upper.to.index).toBe(20);
    expect(top.upper.from.index).toBeLessThan(top.upper.to.index);
  });

  it('uses max(peak1, peak2) for the double-top ceiling and min for the double-bottom floor', () => {
    // قلهٔ اول بالاتر از دوم: مرز بالا باید همان اولی باشد، نه peak2.
    expect(fromDoubleTap(doubleTap({ peak1: point(10, 113) })).upper.from.price).toBe(113);
    // درهٔ اول پایین‌تر از دوم: مرز پایین باید همان اولی باشد.
    expect(fromDoubleTap(doubleBottom({ peak1: point(10, 88) })).lower.from.price).toBe(88);
  });

  it('needs a close above the neckline — not merely above the trough — for a double-bottom success', () => {
    const adapted = fromDoubleTap(doubleBottom());
    // بستهٔ ۹۵ بالای درهٔ ۹۱ است اما زیر خط گردن ۱۰۰: نه پیروزی، نه شکست.
    const belowNeckline = bars(Array.from({ length: 40 }, () => 95));
    expect(outcomeOf(adapted, belowNeckline, 1, PATTERN_CONFIG)).toBe('unresolved');

    const aboveNeckline = bars(Array.from({ length: 40 }, (_, i) => (i === 30 ? 100.5 : 95)));
    expect(outcomeOf(adapted, aboveNeckline, 1, PATTERN_CONFIG)).toBe('success');
  });

  it('drops continuations at the overlap boundary and keeps those beyond it', () => {
    detectors.synthetic = {
      continuation: [
        shaped('cont-inside', 10, 'continuation'),
        shaped('cont-edge', 15, 'continuation'),
        shaped('cont-outside', 16, 'continuation'),
        shaped('cont-far', 30, 'continuation'),
      ],
      reversal: [shaped('rev', 12, 'reversal')],
    };
    const all = detectAllPatterns(monotonic, PATTERN_CONFIG);
    expect(all.some((p) => p.id === 'rev')).toBe(true);
    expect(all.some((p) => p.id === 'cont-inside')).toBe(false); // فاصلهٔ ۲
    expect(all.some((p) => p.id === 'cont-edge')).toBe(false); // فاصلهٔ ۳ = مرز پنجره
    expect(all.some((p) => p.id === 'cont-outside')).toBe(true); // فاصلهٔ ۴
    expect(all.some((p) => p.id === 'cont-far')).toBe(true); // فاصلهٔ ۱۸

    // پنجره از config می‌آید: با پنجرهٔ ۲، همسایهٔ فاصلهٔ ۳ حفظ می‌شود.
    const narrow = detectAllPatterns(monotonic, { ...PATTERN_CONFIG, overlapWindowBars: 2 });
    expect(narrow.some((p) => p.id === 'cont-inside')).toBe(false);
    expect(narrow.some((p) => p.id === 'cont-edge')).toBe(true);
  });

  it('keeps samples whose breakout lands beyond the outcome horizon out of returns (R-PAT-22)', () => {
    // ناحیهٔ بالای مرز ۱۰۱ تا کندل ۲۴، و ناحیهٔ میان مرزها از کندل ۲۵.
    const candles = bars(Array.from({ length: 60 }, (_, i) => (i < 25 ? 102 + i * 0.001 : 100 + (i - 25) * 0.001)));
    const forming: ChartPattern = { ...shaped('current', 50, 'continuation'), status: 'forming' };
    const onTime: ChartPattern[] = [3, 6, 9, 12, 15].map((anchor, k) => ({
      ...shaped(`early-${k}`, anchor, 'continuation'),
      breakoutIndex: anchor + 2,
    }));
    // شکست در ۴۵ یعنی ۱۵ کندل بعد از لنگر ۳۰؛ بیرون از افق ۱۰ کندلیِ نتیجه → حل‌نشده.
    const late: ChartPattern = { ...shaped('late', 30, 'continuation'), breakoutIndex: 45 };

    detectors.synthetic = { continuation: [forming, ...onTime], reversal: [] };
    const baseline = detectAllPatterns(candles, PATTERN_CONFIG).find((p) => p.id === 'current')?.returns;

    detectors.synthetic = { continuation: [forming, ...onTime, late], reversal: [] };
    const withLate = detectAllPatterns(candles, PATTERN_CONFIG).find((p) => p.id === 'current')?.returns;

    expect(baseline?.h1).not.toBeNull();
    expect(withLate).toEqual(baseline);
  });
});
