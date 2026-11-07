// model/patterns/__tests__/outcome.test.ts
import { describe, expect, it } from 'vitest';
import { meanReturns, outcomeOf } from '../outcome';
import { PATTERN_CONFIG } from '../config';
import type { ChartPattern } from '../types';
import type { EngineCandle } from '../../doubleTapEngine';

const point = (index: number, price: number) => ({ index, price, timestamp: index * 60_000 });
const pattern = (over: Partial<ChartPattern> = {}): ChartPattern => ({
  id: 'FLAG_BULL:4:1-2-3-4', kind: 'FLAG_BULL', direction: 'bullish', family: 'continuation',
  anchor: point(4, 105), points: [point(2, 100), point(4, 105)],
  upper: { from: point(4, 106), to: point(4, 106) },
  lower: { from: point(4, 104), to: point(4, 104) },
  target: 112, stopLoss: 98, quality: 60, status: 'forming', ...over,
});
const bars = (closes: number[]): EngineCandle[] => closes.map((close, i) => ({
  timestamp: i * 60_000, open: close, high: close + 0.5, low: close - 0.5, close,
}));

/** الگوی مستطیل: مرزهای افقی ۱۰۴/۱۰۶، ارتفاع ۲، جهت خنثی. */
const neutral = (): ChartPattern => pattern({
  id: 'RECTANGLE:4:1-2-3-4', kind: 'RECTANGLE', direction: 'neutral', family: 'continuation',
});

describe('outcome', () => {
  it('marks a close beyond the directional boundary as success', () => {
    expect(outcomeOf(pattern(), bars([100, 104, 105, 106, 107, 108]), 1, PATTERN_CONFIG)).toBe('success');
  });

  it('marks a close through the opposite boundary as failure', () => {
    expect(outcomeOf(pattern(), bars([100, 104, 105, 103.4, 102, 101]), 1, PATTERN_CONFIG)).toBe('failure');
  });

  it('stays unresolved when nothing happens inside the horizon', () => {
    expect(outcomeOf(pattern(), bars([100, 104, 105, 105, 105.2, 105.4]), 1, PATTERN_CONFIG)).toBe('unresolved');
  });

  it('gives a neutral pattern the direction of its first break and needs half the height', () => {
    // شکست نخست رو به بالا در ۱۰۶.۵؛ نیم‌ارتفاع = ۱ → بستهٔ ۱۰۸ پیروزی است.
    expect(outcomeOf(neutral(), bars([100, 104, 105, 106, 106.5, 107.5, 108]), 1, PATTERN_CONFIG)).toBe('success');
    // همان شکست رو به بالا، اما بستهٔ ۱۰۳ زیرِ مرز مقابل (۱۰۴ منهای بافر ۰.۵) → شکست.
    expect(outcomeOf(neutral(), bars([100, 104, 105, 106, 106.5, 107.5, 103]), 1, PATTERN_CONFIG)).toBe('failure');
  });

  it('floors the neutral target at half an ATR when the pattern has converged', () => {
    // مرزها روی ۱۰۵ به هم رسیده‌اند (ارتفاع ≈ ۰)؛ کفِ هدف ۰.۵×atr = ۰.۵ است.
    const converged = (): ChartPattern => pattern({
      id: 'TRIANGLE_SYM:4:1-2-3-4', kind: 'TRIANGLE_SYM', direction: 'neutral', family: 'continuation',
      upper: { from: point(4, 105), to: point(4, 105) },
      lower: { from: point(4, 105), to: point(4, 105) },
    });
    // شکست در ۱۰۵.۳ (تنها ۰.۳ بالاتر از ورود) پیروزی نیست.
    expect(outcomeOf(converged(), bars([100, 104, 105, 105, 105, 105.3, 105.4]), 1, PATTERN_CONFIG)).toBe('unresolved');
    // ۱۰۵.۶ یعنی ۰.۶ بالاتر از ورود، بیش از ۰.۵×atr → پیروزی.
    expect(outcomeOf(converged(), bars([100, 104, 105, 105, 105, 105.3, 105.6]), 1, PATTERN_CONFIG)).toBe('success');
  });

  it('takes the downside for a neutral first break and needs 0.5 ATR of follow-through', () => {
    // atr = ۴ → هدف = max(ارتفاع/۲ = ۱، ۰.۵×۴ = ۲)؛ شکست زیر ۱۰۴ و بستهٔ ۱۰۲ (۲ پایین‌تر) پیروزی است.
    expect(outcomeOf(neutral(), bars([100, 104, 105, 106, 104, 103.5, 102]), 4, PATTERN_CONFIG)).toBe('success');
  });

  it('reports mean returns as null with fewer than five samples', () => {
    const candles = bars([100, 104, 105, 106, 107, 108, 109, 110, 111, 112]);
    const sample = (anchorIndex: number): ChartPattern => pattern({ anchor: point(anchorIndex, 105), breakoutIndex: anchorIndex });
    const five = [0, 1, 2, 3, 4].map(sample);
    const four = five.slice(0, 4);

    expect(meanReturns(five, candles, PATTERN_CONFIG).h1).not.toBeNull();
    expect(meanReturns(four, candles, PATTERN_CONFIG)).toEqual({ h1: null, h3: null, h5: null });
  });

  it('skips samples without a breakout index instead of fabricating an entry', () => {
    // پنج نمونهٔ تأییدشدهٔ بدون breakoutIndex؛ اگر ورود از لنگر ساخته شود اینجا عدد تولید می‌شد.
    const candles = bars([100, 104, 105, 106, 107, 108, 109, 110, 111, 112]);
    const samples = [0, 1, 2, 3, 4].map(() => pattern({ status: 'confirmed' }));

    expect(meanReturns(samples, candles, PATTERN_CONFIG)).toEqual({ h1: null, h3: null, h5: null });
  });

  it('gives bearish samples a positive return when price falls after the break', () => {
    // شکست نزولی در کندل ۴ (مرز پایین ۱۰۴) و بستهٔ ۱۰۲ در کندل ۵ → بازده مثبت.
    const candles = bars([110, 108, 106, 105, 104, 102, 101, 100, 99, 98]);
    const samples = [0, 1, 2, 3, 4].map(() => pattern({ direction: 'bearish', breakoutIndex: 4 }));
    const h1 = meanReturns(samples, candles, PATTERN_CONFIG).h1 ?? Number.NaN;

    expect(h1).toBeGreaterThan(0);
    expect(h1).toBeCloseTo(((104 - 102) / 104) * 100);
  });
});
