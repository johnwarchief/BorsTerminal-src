// model/patterns/outcome.ts
import type { EngineCandle } from '../doubleTapEngine';
import type { PatternConfig } from './config';
import type { ChartPattern } from './types';
import { lineValue } from './geometry';

export type PatternOutcome = 'success' | 'failure' | 'unresolved';

function heightOf(pattern: ChartPattern): number {
  return Math.abs(lineValue(pattern.upper, pattern.anchor.index) - lineValue(pattern.lower, pattern.anchor.index));
}

export function outcomeOf(
  pattern: ChartPattern,
  candles: readonly EngineCandle[],
  atr: number,
  config: PatternConfig,
  horizon = config.outcomeHorizon,
): PatternOutcome {
  const start = pattern.anchor.index + 1;
  const end = Math.min(candles.length, start + horizon);
  const buffer = config.invalidationBufferAtr * atr;

  if (pattern.direction === 'neutral') {
    const height = heightOf(pattern);
    const target = Math.max(height / 2, config.neutralMinTargetAtr * atr);
    let bias: 'up' | 'down' | null = null;
    let entry = 0;
    for (let i = start; i < end; i++) {
      const close = candles[i].close;
      const up = lineValue(pattern.upper, i);
      const down = lineValue(pattern.lower, i);
      if (!bias) {
        if (close > up) { bias = 'up'; entry = up; }
        else if (close < down) { bias = 'down'; entry = down; }
        continue;
      }
      if (bias === 'up') {
        if (close >= entry + target) return 'success';
        if (close < down - buffer) return 'failure';
      } else {
        if (close <= entry - target) return 'success';
        if (close > up + buffer) return 'failure';
      }
    }
    return 'unresolved';
  }

  const bullish = pattern.direction === 'bullish';
  for (let i = start; i < end; i++) {
    const close = candles[i].close;
    const up = lineValue(pattern.upper, i);
    const down = lineValue(pattern.lower, i);
    if (bullish ? close > up : close < down) return 'success';
    if (bullish ? close < down - buffer : close > up + buffer) return 'failure';
  }
  return 'unresolved';
}

/** میانگین بازدهِ ۱/۳/۵ کندلِ نمونه‌های حل‌شده؛ زیرِ returnsMinSamples نمونه null. */
export function meanReturns(
  samples: readonly ChartPattern[],
  candles: readonly EngineCandle[],
  config: PatternConfig,
): { h1: number | null; h3: number | null; h5: number | null } {
  const directional = samples.filter((p) => p.direction !== 'neutral');
  const result = { h1: null as number | null, h3: null as number | null, h5: null as number | null };
  for (const horizon of config.returnHorizons) {
    const values: number[] = [];
    for (const sample of directional) {
      const triggerIndex = sample.breakoutIndex;
      if (triggerIndex === undefined) continue;
      const end = triggerIndex + horizon;
      if (end >= candles.length) continue;
      const trigger = sample.direction === 'bullish'
        ? lineValue(sample.upper, triggerIndex)
        : lineValue(sample.lower, triggerIndex);
      if (!(trigger > 0)) continue;
      const close = candles[end].close;
      values.push(((sample.direction === 'bullish' ? close - trigger : trigger - close) / trigger) * 100);
    }
    const mean = values.length >= config.returnsMinSamples
      ? values.reduce((a, b) => a + b, 0) / values.length
      : null;
    if (horizon === 1) result.h1 = mean;
    if (horizon === 3) result.h3 = mean;
    if (horizon === 5) result.h5 = mean;
  }
  return result;
}
