import { describe, expect, it } from 'vitest';
import { estimatePatternFormation } from '../formation';
import { PATTERN_CONFIG } from '../config';
import type { ChartPattern } from '../types';
import { laplaceRate, wilsonInterval } from '../../doubleTapEngine';
import type { EngineCandle } from '../../doubleTapEngine';

const point = (index: number, price: number) => ({ index, price, timestamp: index * 60_000 });

const pattern = (
  id: string,
  anchorIndex: number,
  status: ChartPattern['status'],
  quality = 60,
  family: ChartPattern['family'] = 'continuation',
): ChartPattern => ({
  id,
  kind: family === 'reversal' ? 'HEAD_SHOULDERS' : 'FLAG_BULL',
  direction: family === 'reversal' ? 'bearish' : 'bullish',
  family,
  anchor: point(anchorIndex, 105),
  points: [point(anchorIndex - 1, 100), point(anchorIndex, 105)],
  upper: { from: point(anchorIndex, 106), to: point(anchorIndex, 106) },
  lower: { from: point(anchorIndex, 104), to: point(anchorIndex, 104) },
  target: 112, stopLoss: 98, quality, status,
});

/** کندل‌های تخت با close دلخواه؛ مرزهای ۱۰۴/۱۰۶ و atr=1 نتیجه را قطعی می‌کنند. */
const candlesWith = (length: number, closeAt: (i: number) => number): EngineCandle[] =>
  Array.from({ length }, (_, i) => {
    const close = closeAt(i);
    return { timestamp: i * 60_000, open: close, high: close + 0.5, low: close - 0.5, close };
  });

/** ناحیهٔ پیروزی (بالای ۱۰۶) تا کندل ۲۰۰ و ناحیهٔ شکست (زیر ۱۰۳.۵) بعد از آن. */
const outcomeRegions = (): EngineCandle[] => candlesWith(400, (i) => (i < 200 ? 110 : 100));

const anchors = (count: number, start: number, step: number): number[] =>
  Array.from({ length: count }, (_, k) => start + k * step);

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

  it('feeds laplaceRate and wilsonInterval from the resolved successes and failures', () => {
    const candles = outcomeRegions();
    const samples = [
      ...anchors(6, 0, 12).map((a, k) => pattern(`win-${k}`, a, 'confirmed')),
      ...anchors(4, 210, 12).map((a, k) => pattern(`loss-${k}`, a, 'confirmed')),
    ];
    const current = pattern('current', 390, 'forming');
    const estimate = estimatePatternFormation(current, [current, ...samples], candles, 1, PATTERN_CONFIG);

    expect(estimate?.successes).toBe(6);
    expect(estimate?.failures).toBe(4);
    expect(estimate?.probability).toBe(laplaceRate(6, 4));
    expect(estimate?.intervalLow).toBe(wilsonInterval(6, 10)[0]);
    expect(estimate?.intervalHigh).toBe(wilsonInterval(6, 10)[1]);
  });

  it('turns probability on exactly at formationMinResolved (7 → null, 8 → number)', () => {
    const candles = outcomeRegions();
    const wins = (count: number) => anchors(count, 0, 12).map((a, k) => pattern(`win-${k}`, a, 'confirmed'));
    const current = pattern('current', 390, 'forming');
    const seven = estimatePatternFormation(current, [current, ...wins(7)], candles, 1, PATTERN_CONFIG);
    const eight = estimatePatternFormation(current, [current, ...wins(8)], candles, 1, PATTERN_CONFIG);

    expect(seven?.resolved).toBe(7);
    expect(seven?.probability).toBeNull();
    expect(eight?.resolved).toBe(8);
    expect(eight?.probability).toBe(laplaceRate(8, 0));

    // آستانه از config می‌آید، نه از عدد جادویی ۸.
    const early = estimatePatternFormation(
      current, [current, ...wins(7)], candles, 1, { ...PATTERN_CONFIG, formationMinResolved: 7 },
    );
    expect(early?.probability).not.toBeNull();
  });

  it('derives quality terciles from resolved samples, not from unresolved ones', () => {
    // سه ناحیه: پیروزی (۱۱۰)، شکست (۱۰۰)، حل‌نشده (۱۰۵).
    const candles = candlesWith(400, (i) => (i < 200 ? 110 : i < 300 ? 100 : 105));
    const wins = anchors(8, 0, 12).map((a, k) => pattern(`win-${k}`, a, 'confirmed', 100));
    const midFailures = anchors(8, 200, 12).map((a, k) => pattern(`mid-${k}`, a, 'confirmed', 50));
    const lowFailures = anchors(8, 201, 12).map((a, k) => pattern(`low-${k}`, a, 'confirmed', 10));
    const unresolved = anchors(8, 300, 12).map((a, k) => pattern(`open-${k}`, a, 'confirmed', 0));
    const current = pattern('current', 390, 'forming', 10);
    const estimate = estimatePatternFormation(
      current, [current, ...wins, ...midFailures, ...lowFailures, ...unresolved], candles, 1, PATTERN_CONFIG,
    );

    // ترسیل ۰ فقط از روی ۲۴ نمونهٔ حل‌شده بسته می‌شود: کیفیت‌های ۱۰ و ۵۰ هر دو در آن می‌افتند.
    expect(estimate?.qualityBucket).toBe(0);
    expect(estimate?.successes).toBe(0);
    expect(estimate?.failures).toBe(16);
  });

  it('switches to a quality bucket once that bucket has enough resolved samples', () => {
    const candles = outcomeRegions();
    const samples = [
      ...anchors(10, 0, 12).map((a, k) => pattern(`high-win-${k}`, a, 'confirmed', 100)),
      ...anchors(10, 200, 12).map((a, k) => pattern(`low-loss-${k}`, a, 'confirmed', 10)),
      ...anchors(10, 201, 12).map((a, k) => pattern(`mid-loss-${k}`, a, 'confirmed', 50)),
    ];
    const highCurrent = pattern('current-high', 390, 'forming', 100);
    const lowCurrent = pattern('current-low', 388, 'forming', 10);
    const high = estimatePatternFormation(highCurrent, [highCurrent, ...samples], candles, 1, PATTERN_CONFIG);
    const low = estimatePatternFormation(lowCurrent, [lowCurrent, ...samples], candles, 1, PATTERN_CONFIG);

    // کل نمونه‌ها: ۱۰ پیروزی، ۲۰ شکست. ترسیل ۱۰۰ فقط پیروزی‌ها و ترسیل ۱۰ فقط شکست‌ها را دارد.
    expect(high?.qualityBucket).toBe(1);
    expect(high?.successes).toBe(10);
    expect(high?.failures).toBe(0);
    expect(low?.qualityBucket).toBe(0);
    expect(low?.successes).toBe(0);
    expect(low?.failures).toBe(20);
  });

  it('never counts unresolved samples as failures', () => {
    // ناحیهٔ ۱۰۰ = شکست، ناحیهٔ ۱۰۵ = میان مرزها و حل‌نشده.
    const candles = candlesWith(400, (i) => (i < 150 ? 100 : 105));
    const failures = anchors(3, 5, 12).map((a, k) => pattern(`loss-${k}`, a, 'confirmed'));
    const unresolved = anchors(5, 160, 12).map((a, k) => pattern(`open-${k}`, a, 'confirmed'));
    const current = pattern('current', 390, 'forming');
    const estimate = estimatePatternFormation(current, [current, ...failures, ...unresolved], candles, 1, PATTERN_CONFIG);

    expect(estimate?.resolved).toBe(3);
    expect(estimate?.successes).toBe(0);
    expect(estimate?.failures).toBe(3);
    expect(estimate?.probability).toBeNull();
  });

  it('pools samples by family: continuation counts for continuations, reversal does not', () => {
    const candles = candlesWith(100, () => 110);
    const continuationSample = pattern('sample-continuation', 5, 'confirmed');
    const reversalSample = pattern('sample-reversal', 8, 'confirmed', 60, 'reversal');

    const continuationCurrent = pattern('current-continuation', 90, 'forming');
    const continuation = estimatePatternFormation(
      continuationCurrent, [continuationCurrent, continuationSample, reversalSample], candles, 1, PATTERN_CONFIG,
    );
    expect(continuation?.resolved).toBe(1);
    expect(continuation?.successes).toBe(1);
    expect(continuation?.failures).toBe(0);

    const reversalCurrent = pattern('current-reversal', 90, 'forming', 60, 'reversal');
    const reversal = estimatePatternFormation(
      reversalCurrent, [reversalCurrent, continuationSample, reversalSample], candles, 1, PATTERN_CONFIG,
    );
    expect(reversal?.resolved).toBe(1);
    expect(reversal?.successes).toBe(0);
    expect(reversal?.failures).toBe(1);
  });
});
