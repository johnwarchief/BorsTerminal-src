// model/patterns/registry.ts
import type { EngineCandle } from '../doubleTapEngine';
import { calculateAtr, DEFAULT_PRECISION_PARAMS, detectDoubleTapPatterns } from '../doubleTapEngine';
import type { DoubleTapPattern } from '../types';
import { PATTERN_CONFIG, type PatternConfig } from './config';
import type { ChartPattern, PatternKind, PatternTier } from './types';
import { detectContinuation } from './detectContinuation';
import { detectReversal } from './detectReversal';
import { detectCupRounding } from './detectCupRounding';
import { detectTier2 } from './detectTier2';
import { estimatePatternFormation, estimateReturns } from './formation';
import { outcomeOf, type PatternOutcome } from './outcome';

/**
 * ردهٔ پذیرش هر گونه: ردهٔ ۱ پذیرش کامل، ردهٔ ۲ کم‌بسامد با برچسب.
 * `Record<PatternKind, …>` exhaustiveness را در زمان کامپایل تضمین می‌کند.
 */
export const PATTERN_TIER: Record<PatternKind, PatternTier> = {
  DOUBLE_TOP: 1, DOUBLE_BOTTOM: 1, HEAD_SHOULDERS: 1, INVERSE_HEAD_SHOULDERS: 1,
  TRIPLE_TOP: 1, TRIPLE_BOTTOM: 1, FLAG_BULL: 1, FLAG_BEAR: 1, PENNANT: 1,
  TRIANGLE_ASC: 1, TRIANGLE_DESC: 1, TRIANGLE_SYM: 1, RECTANGLE: 1,
  WEDGE_RISING: 1, WEDGE_FALLING: 1, CUP_HANDLE: 1, INVERSE_CUP_HANDLE: 1,
  ROUNDING_TOP: 1, ROUNDING_BOTTOM: 1,
  DIAMOND_TOP: 2, DIAMOND_BOTTOM: 2, BROADENING_TOP: 2, BROADENING_BOTTOM: 2,
  ISLAND_REVERSAL: 2, THREE_RISING_PEAKS: 2, THREE_FALLING_PEAKS: 2,
};

export function fromDoubleTap(p: DoubleTapPattern): ChartPattern {
  const anchor = p.retest ?? p.peak2;
  const bullish = p.type === 'DOUBLE_BOTTOM';
  const at = (index: number, price: number, timestamp: number) => ({ index, price, timestamp });
  // R-PAT-21: مرزها بر اساس جهت مرتب می‌شوند. در دوقلوی کف، خط گردن بالاتر از درهٔ دوم است؛
  // در دوقلوی سقف، قلهٔ دوم بالاتر از خط گردن. upper همیشه قیمت بزرگ‌تر و lower قیمت کوچک‌تر است.
  // مرزِ قله/دره از max/min هر دو قله/دره ساخته می‌شود تا هر دو سرِ الگو درونِ مرز بمانند.
  const peakHigh = p.peak1.price >= p.peak2.price ? p.peak1 : p.peak2;
  const peakLow = p.peak1.price <= p.peak2.price ? p.peak1 : p.peak2;
  const upperSource = bullish ? p.neckline : peakHigh;
  const lowerSource = bullish ? peakLow : p.neckline;
  // مرزهای افقی از peak1 تا لنگر کشیده می‌شوند؛ خطِ تک‌نقطه‌ای هیچ‌وقت روی چارت رسم نمی‌شد.
  const horizontal = (price: number, timestamp: number) => ({
    from: at(p.peak1.index, price, p.peak1.timestamp),
    to: at(anchor.index, price, timestamp),
  });
  return {
    id: `DT:${p.id}`,
    kind: p.type,
    direction: bullish ? 'bullish' : 'bearish',
    family: 'reversal',
    anchor: at(anchor.index, anchor.price, anchor.timestamp),
    points: [p.peak1, p.neckline, p.peak2].map((x) => at(x.index, x.price, x.timestamp)),
    upper: horizontal(upperSource.price, upperSource.timestamp),
    lower: horizontal(lowerSource.price, lowerSource.timestamp),
    // R-PAT-19: بازدهِ الگوی بازگشتی از شکست واقعی دوقلو اندازه‌گیری می‌شود، نه از لنگر.
    breakoutIndex: p.breakoutIndex,
    target: p.target1,
    stopLoss: p.stopLoss,
    quality: p.quality,
    // آداپتر دوقلو همیشه ردهٔ یک است؛ جدول مرکزی هم همین را تحمیل می‌کند.
    tier: 1,
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
    ...detectCupRounding(candles, atr, config),
    ...detectTier2(candles, atr, config),
    ...detectDoubleTapPatterns(candles, DEFAULT_PRECISION_PARAMS).map(fromDoubleTap),
  ].filter((p, i, all) => all.findIndex((x) => x.id === p.id) === i);

  // R-PAT-6: بازگشتی بر ادامه‌دهنده اولویت دارد؛ ادامه‌دهندهٔ لنگرِ نزدیک (تا پنجرهٔ config) حذف می‌شود.
  const reversals = merged.filter((p) => p.family === 'reversal');
  const withoutOverlaps = merged
    .filter(
      (p) => p.family === 'reversal'
        || !reversals.some((r) => Math.abs(r.anchor.index - p.anchor.index) <= config.overlapWindowBars),
    )
    // ردهٔ هر نمونه یک‌جا از جدول می‌آید؛ دتکتورها هم ردهٔ خود را اعلام می‌کنند و این نقشه مرجع نهایی است.
    .map((p) => ({ ...p, tier: PATTERN_TIER[p.kind] }));

  // R-PAT-22: نتیجهٔ هر نمونه یک‌بار محاسبه می‌شود و فقط نمونه‌های حل‌شده به تخمین بازده می‌رسند.
  const outcomes = new Map<string, PatternOutcome>(
    withoutOverlaps.map((p): [string, PatternOutcome] => [p.id, outcomeOf(p, candles, atr, config)]),
  );
  const resolvedIds: ReadonlySet<string> = new Set(
    [...outcomes].filter(([, outcome]) => outcome !== 'unresolved').map(([id]) => id),
  );

  return withoutOverlaps
    .map((pattern) => (pattern.status === 'forming'
      ? {
          ...pattern,
          formation: estimatePatternFormation(pattern, withoutOverlaps, candles, atr, config) ?? undefined,
          returns: estimateReturns(pattern, withoutOverlaps, candles, config, resolvedIds),
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
