// model/patterns/registry.ts
import type { EngineCandle } from '../doubleTapEngine';
import { calculateAtr, DEFAULT_PRECISION_PARAMS, detectDoubleTapPatterns } from '../doubleTapEngine';
import type { DoubleTapPattern } from '../types';
import { PATTERN_CONFIG, type PatternConfig } from './config';
import type { ChartPattern } from './types';
import { detectContinuation } from './detectContinuation';
import { detectReversal } from './detectReversal';
import { estimatePatternFormation, estimateReturns } from './formation';

export function fromDoubleTap(p: DoubleTapPattern): ChartPattern {
  const anchor = p.retest ?? p.peak2;
  const bullish = p.type === 'DOUBLE_BOTTOM';
  const at = (index: number, price: number, timestamp: number) => ({ index, price, timestamp });
  return {
    id: `DT:${p.id}`,
    kind: p.type,
    direction: bullish ? 'bullish' : 'bearish',
    family: 'reversal',
    anchor: at(anchor.index, anchor.price, anchor.timestamp),
    points: [p.peak1, p.neckline, p.peak2].map((x) => at(x.index, x.price, x.timestamp)),
    upper: { from: at(p.peak2.index, p.peak2.price, p.peak2.timestamp), to: at(p.peak2.index, p.peak2.price, p.peak2.timestamp) },
    lower: { from: at(p.neckline.index, p.neckline.price, p.neckline.timestamp), to: at(p.neckline.index, p.neckline.price, p.neckline.timestamp) },
    // R-PAT-19: بازدهِ الگوی بازگشتی از شکست واقعی دوقلو اندازه‌گیری می‌شود، نه از لنگر.
    breakoutIndex: p.breakoutIndex,
    target: p.target1,
    stopLoss: p.stopLoss,
    quality: p.quality,
    status: p.status === 'forming' ? 'forming' : p.status === 'invalidated' ? 'invalidated' : 'confirmed',
    formation: p.formation,
  };
}

export function detectAllPatterns(
  candles: readonly EngineCandle[],
  config: PatternConfig = PATTERN_CONFIG,
): ChartPattern[] {
  const atrSeries = calculateAtr(candles, config.atrPeriod);
  const atr = atrSeries[atrSeries.length - 1] ?? 0;
  if (!(atr > 0)) return [];
  const merged = [
    ...detectContinuation(candles, atr, config),
    ...detectReversal(candles, atr, config),
    ...detectDoubleTapPatterns(candles, DEFAULT_PRECISION_PARAMS).map(fromDoubleTap),
  ].filter((p, i, all) => all.findIndex((x) => x.id === p.id) === i);

  // R-PAT-6: بازگشتی بر ادامه‌دهنده اولویت دارد؛ ادامه‌دهندهٔ لنگرِ نزدیک (≤ ۳ کندل) حذف می‌شود.
  const reversals = merged.filter((p) => p.family === 'reversal');
  const withoutOverlaps = merged.filter(
    (p) => p.family === 'reversal' || !reversals.some((r) => Math.abs(r.anchor.index - p.anchor.index) <= 3),
  );

  return withoutOverlaps
    .map((pattern) => (pattern.status === 'forming'
      ? {
          ...pattern,
          formation: estimatePatternFormation(pattern, withoutOverlaps, candles, atr, config) ?? undefined,
          returns: estimateReturns(pattern, withoutOverlaps, candles, config),
        }
      : pattern))
    .sort((a, b) => a.anchor.index - b.anchor.index);
}

/** حداکثر شش شکل: آخرین «در حال تشکیل» و آخرین «تأییدشده» هر خانواده. */
export function selectFeaturedPatterns(
  patterns: readonly ChartPattern[],
  max = 6,
): ChartPattern[] {
  const picked: ChartPattern[] = [];
  for (const family of ['reversal', 'continuation'] as const) {
    const familyPatterns = patterns.filter((p) => p.family === family);
    const forming = [...familyPatterns].filter((p) => p.status === 'forming').sort((a, b) => b.anchor.index - a.anchor.index)[0];
    const confirmed = [...familyPatterns].filter((p) => p.status === 'confirmed').sort((a, b) => b.anchor.index - a.anchor.index)[0];
    if (forming) picked.push(forming);
    if (confirmed) picked.push(confirmed);
  }
  return picked.sort((a, b) => b.anchor.index - a.anchor.index).slice(0, max);
}
