// model/patterns/formation.ts
import type { EngineCandle } from '../doubleTapEngine';
import { confidenceFor, laplaceRate, wilsonInterval } from '../doubleTapEngine';
import type { FormationEstimate } from '../types';
import type { PatternConfig } from './config';
import type { ChartPattern } from './types';
import { meanReturns, outcomeOf } from './outcome';

export function estimatePatternFormation(
  current: ChartPattern,
  all: readonly ChartPattern[],
  candles: readonly EngineCandle[],
  atr: number,
  config: PatternConfig,
): FormationEstimate | null {
  if (current.status !== 'forming') return null;

  // R-PAT-1: نمونه‌ها از همان خانواده (ادامه‌دهنده/بازگشتی)، نه فقط همان نوع.
  const samples = all.filter(
    (p) => p.id !== current.id && p.family === current.family && p.status !== 'forming'
      && p.anchor.index + 1 < candles.length,
  );
  const resolved = samples
    .map((sample) => ({ sample, outcome: outcomeOf(sample, candles, atr, config) }))
    .filter((item): item is { sample: ChartPattern; outcome: 'success' | 'failure' } => item.outcome !== 'unresolved');

  // R-PAT-20: آستانه‌های ترسیل کیفیت از config خوانده می‌شوند، نه از عدد جادویی.
  // ترسیل‌ها فقط روی نمونه‌های حل‌شده بسته می‌شوند تا نمونه‌های حل‌نشده کیفیت‌های بی‌مصرف را وارد نکنند.
  const qualities = resolved.map((item) => item.sample.quality).sort((a, b) => a - b);
  let selected = resolved;
  let qualityBucket: number | undefined;
  if (qualities.length >= config.formationMinResolved) {
    const low = qualities[Math.floor(qualities.length / 3)]!;
    const high = qualities[Math.floor((2 * qualities.length) / 3)]!;
    const bucket = current.quality <= low ? 0 : current.quality <= high ? 1 : 2;
    const bucketOf = (q: number) => (q <= low ? 0 : q <= high ? 1 : 2);
    const bucketSamples = resolved.filter((item) => bucketOf(item.sample.quality) === bucket);
    if (bucketSamples.length >= config.formationMinResolved) {
      selected = bucketSamples;
      qualityBucket = bucket;
    }
  }

  const successes = selected.filter((item) => item.outcome === 'success').length;
  const failures = selected.length - successes;
  const count = successes + failures;
  return {
    probability: count >= config.formationMinResolved ? laplaceRate(successes, failures) : null,
    successes,
    failures,
    resolved: count,
    confidence: confidenceFor(count),
    horizon: config.outcomeHorizon,
    method: 'same-symbol',
    qualityBucket,
    intervalLow: count > 0 ? wilsonInterval(successes, count)[0] : undefined,
    intervalHigh: count > 0 ? wilsonInterval(successes, count)[1] : undefined,
  };
}

export function estimateReturns(
  current: ChartPattern,
  all: readonly ChartPattern[],
  candles: readonly EngineCandle[],
  config: PatternConfig,
  resolvedIds: ReadonlySet<string>,
): ChartPattern['returns'] {
  if (current.status !== 'forming') return undefined;
  // R-PAT-22: فقط نمونه‌های حل‌شده در بازده سهم دارند؛ نمونهٔ حل‌نشده (مثلاً شکست بعد از افق) کنار می‌رود.
  const samples = all.filter((p) => p.id !== current.id && p.family === current.family
    && p.status !== 'forming' && resolvedIds.has(p.id));
  return meanReturns(samples, candles, config);
}
