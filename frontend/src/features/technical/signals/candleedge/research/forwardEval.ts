import type {
  ForwardBar,
  ForwardEvent,
  ForwardOutcome,
  ForwardPeriod,
  ForwardRow,
} from './types';

export const FORWARD_HORIZONS = [3, 5, 10, 20] as const;
/** Set before any final evaluation result was produced (2026-10-25). */
export const EVAL_CUTOFF_MS = Date.UTC(2026, 3, 1);
export const FORWARD_NOTE =
  'بازدهِ ناخالصِ تشخیصی؛ بدون هزینه، اسلیپیج، صف یا مدلِ نقدشوندگی — بک‌تستِ سوددهی نیست.';

export interface ForwardOptions {
  seriesKey: string;
  bars: readonly ForwardBar[];
  events: readonly ForwardEvent[];
  cutoffMs?: number;
  marketBaseline?: (entryTime: number, horizon: number) => number | undefined;
}

export interface ForwardResult {
  seriesKey: string;
  horizons: number[];
  cutoffMs: number;
  rows: ForwardRow[];
  eventsEvaluated: number;
  skippedNeutral: number;
  invalidEvents: number;
  outcomes: ForwardOutcome[];
  note: string;
}

export interface ReturnsSummary {
  n: number;
  mean: number | null;
  median: number | null;
  q05: number | null;
  q25: number | null;
  q50: number | null;
  q75: number | null;
  q95: number | null;
  sd: number | null;
  winRate: number | null;
  winRateCI: [number, number] | null;
  meanCI: [number, number] | null;
  lowSample: boolean;
}

/**
 * Symbol-clustered bootstrap. Events inside one symbol overlap in time, so
 * resampling events (iid) would understate uncertainty; resampling symbols
 * keeps each symbol's overlapping event block together.
 */
export function clusterBootstrapMeanCI(
  groups: readonly (readonly number[])[],
  seedText: string,
  iterations = 1000,
): [number, number] | null {
  const nonEmpty = groups.filter((g) => g.length > 0);
  if (nonEmpty.length === 0) return null;
  if (nonEmpty.length === 1) {
    const only = mean(nonEmpty[0]);
    return only === null ? null : [only, only];
  }
  const rand = mulberry32(seedFrom(seedText));
  const means: number[] = [];
  for (let i = 0; i < iterations; i += 1) {
    let sum = 0;
    let count = 0;
    for (let j = 0; j < nonEmpty.length; j += 1) {
      const group = nonEmpty[Math.floor(rand() * nonEmpty.length)];
      for (const value of group) {
        sum += value;
        count += 1;
      }
    }
    means.push(sum / count);
  }
  means.sort((a, b) => a - b);
  return [quantile(means, 0.025)!, quantile(means, 0.975)!];
}

export function summarizeReturns(values: readonly number[], seedText: string): ReturnsSummary {
  const sorted = [...values].sort((a, b) => a - b);
  const n = values.length;
  const wins = values.filter((v) => v > 0).length;
  return {
    n,
    mean: mean(values),
    median: quantile(sorted, 0.5),
    q05: quantile(sorted, 0.05),
    q25: quantile(sorted, 0.25),
    q50: quantile(sorted, 0.5),
    q75: quantile(sorted, 0.75),
    q95: quantile(sorted, 0.95),
    sd: sampleSd(values),
    winRate: n ? wins / n : null,
    winRateCI: n ? wilson(wins, n) : null,
    meanCI: bootstrapMeanCI(values, seedText),
    lowSample: n < 30,
  };
}

interface Bucket {
  detector: string;
  horizon: number;
  period: ForwardPeriod;
  direction: 1 | -1;
  returns: number[];
  market: number[];
  rightCensored: number;
}

function mean(values: readonly number[]): number | null {
  if (values.length === 0) return null;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

function quantile(sorted: readonly number[], p: number): number | null {
  if (sorted.length === 0) return null;
  if (sorted.length === 1) return sorted[0];
  const pos = (sorted.length - 1) * p;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}

function sampleSd(values: readonly number[]): number | null {
  if (values.length < 2) return null;
  const m = mean(values)!;
  const variance =
    values.reduce((acc, v) => acc + (v - m) * (v - m), 0) / (values.length - 1);
  return Math.sqrt(variance);
}

function wilson(k: number, n: number): [number, number] {
  const z = 1.96;
  const phat = k / n;
  const denom = 1 + (z * z) / n;
  const center = (phat + (z * z) / (2 * n)) / denom;
  const half =
    (z * Math.sqrt((phat * (1 - phat)) / n + (z * z) / (4 * n * n))) / denom;
  return [Math.max(0, center - half), Math.min(1, center + half)];
}

function seedFrom(text: string): number {
  let h = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function mulberry32(seed: number): () => number {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function bootstrapMeanCI(
  values: readonly number[],
  seedText: string,
  iterations = 1000,
): [number, number] | null {
  if (values.length === 0) return null;
  if (values.length === 1) return [values[0], values[0]];
  const rand = mulberry32(seedFrom(seedText));
  const means: number[] = [];
  for (let i = 0; i < iterations; i += 1) {
    let sum = 0;
    for (let j = 0; j < values.length; j += 1) {
      sum += values[Math.floor(rand() * values.length)];
    }
    means.push(sum / values.length);
  }
  means.sort((a, b) => a - b);
  return [quantile(means, 0.025)!, quantile(means, 0.975)!];
}

function periodOf(time: number, cutoffMs: number): ForwardPeriod {
  return time < cutoffMs ? 'discovery' : 'evaluation';
}

/**
 * Causal forward diagnostic: entry is the open of the bar after confirmation,
 * exit is the close of the H-th bar after entry. The confirmation bar's close
 * is never used as an obtainable entry price. No parameter is selected here.
 */
export function evaluateForward(options: ForwardOptions): ForwardResult {
  const cutoffMs = options.cutoffMs ?? EVAL_CUTOFF_MS;
  const { bars, events } = options;
  const horizons = [...FORWARD_HORIZONS];
  const baselineRaw = new Map<string, number[]>();
  for (let t = 0; t < bars.length; t += 1) {
    const period = periodOf(bars[t].time, cutoffMs);
    for (const horizon of horizons) {
      const exit = t + horizon - 1;
      if (exit >= bars.length || !(bars[t].open > 0)) continue;
      const key = `${period}|${horizon}`;
      const bucket = baselineRaw.get(key);
      const value = bars[exit].close / bars[t].open - 1;
      if (bucket) bucket.push(value);
      else baselineRaw.set(key, [value]);
    }
  }

  const buckets = new Map<string, Bucket>();
  const outcomes: ForwardOutcome[] = [];
  let skippedNeutral = 0;
  let invalidEvents = 0;
  let eventsEvaluated = 0;

  for (const event of events) {
    if (event.bias !== 'bullish' && event.bias !== 'bearish') {
      skippedNeutral += 1;
      continue;
    }
    if (
      !Number.isInteger(event.confirmedAtIndex) ||
      event.confirmedAtIndex < 0 ||
      event.confirmedAtIndex >= bars.length
    ) {
      invalidEvents += 1;
      continue;
    }
    const direction = event.bias === 'bullish' ? 1 : -1;
    const confirmedTime = Number.isFinite(event.confirmedAt)
      ? event.confirmedAt
      : bars[event.confirmedAtIndex].time;
    const entry = event.confirmedAtIndex + 1;
    // Split by the entry bar, not the confirmation bar: an event confirmed on
    // the last discovery day but entered after the cutoff belongs to evaluation.
    const period = periodOf(
      entry < bars.length ? bars[entry].time : confirmedTime,
      cutoffMs,
    );
    eventsEvaluated += 1;

    for (const horizon of horizons) {
      const key = `${event.detector}|${horizon}|${period}`;
      let bucket = buckets.get(key);
      if (!bucket) {
        bucket = {
          detector: event.detector,
          horizon,
          period,
          direction,
          returns: [],
          market: [],
          rightCensored: 0,
        };
        buckets.set(key, bucket);
      }
      const exit = entry + horizon - 1;
      if (entry >= bars.length || exit >= bars.length || !(bars[entry].open > 0)) {
        bucket.rightCensored += 1;
        continue;
      }
      const returnPct = (bars[exit].close / bars[entry].open - 1) * direction;
      bucket.returns.push(returnPct);
      const localRaw = baselineRaw.get(`${period}|${horizon}`) ?? [];
      const localMean = mean(localRaw);
      outcomes.push({
        symbol: options.seriesKey.split('|')[0] ?? '',
        detector: event.detector,
        horizon,
        period,
        entryTime: bars[entry].time,
        returnPct,
        baselineLocal: localMean === null ? null : localMean * direction,
      });
      const market = options.marketBaseline?.(bars[entry].time, horizon);
      if (typeof market === 'number' && Number.isFinite(market)) {
        bucket.market.push(market);
      }
    }
  }

  const rows: ForwardRow[] = [];
  for (const bucket of buckets.values()) {
    const summary = summarizeReturns(
      bucket.returns,
      `${options.seriesKey}|${bucket.detector}|${bucket.horizon}|${bucket.period}`,
    );
    const localRaw = baselineRaw.get(`${bucket.period}|${bucket.horizon}`) ?? [];
    const localMean = mean(localRaw);
    const directionalLocal =
      localMean === null ? null : localMean * bucket.direction;
    const marketMean = mean(bucket.market);
    rows.push({
      detector: bucket.detector,
      horizon: bucket.horizon,
      period: bucket.period,
      n: summary.n,
      rightCensored: bucket.rightCensored,
      mean: summary.mean,
      median: summary.median,
      q05: summary.q05,
      q25: summary.q25,
      q50: summary.q50,
      q75: summary.q75,
      q95: summary.q95,
      sd: summary.sd,
      winRate: summary.winRate,
      winRateCI: summary.winRateCI,
      meanCI: summary.meanCI,
      baselineLocalMean: directionalLocal,
      baselineLocalN: localRaw.length,
      baselineMarketMean: marketMean,
      marketBaselineN: bucket.market.length,
      deltaLocal:
        summary.mean === null || directionalLocal === null
          ? null
          : summary.mean - directionalLocal,
      deltaMarket:
        summary.mean === null || marketMean === null
          ? null
          : summary.mean - marketMean,
      lowSample: summary.lowSample,
      entryRule: 'next-bar-open',
      exitRule: 'horizon-close',
      note: FORWARD_NOTE,
    });
  }

  rows.sort(
    (a, b) =>
      a.detector.localeCompare(b.detector) ||
      a.horizon - b.horizon ||
      a.period.localeCompare(b.period),
  );

  return {
    seriesKey: options.seriesKey,
    horizons,
    cutoffMs,
    rows,
    eventsEvaluated,
    skippedNeutral,
    invalidEvents,
    outcomes,
    note: FORWARD_NOTE,
  };
}
