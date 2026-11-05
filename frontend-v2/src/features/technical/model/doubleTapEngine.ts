/**
 * frontend-v2/src/features/technical/model/doubleTapEngine.ts
 *
 * موتور خالص و تست‌پذیر الگوی سقف/کف دوقلو (M/W):
 * - تشخیص با پیوت تأییدشده، تلورانس ATR، عمق خط گردن و سرکوب هم‌پوشانی
 * - تارگت اندازه‌گیری‌شده + توسعهٔ ۱٫۶۱۸ و حد ضرر
 * - احتمال تشکیل ترکیبی: نرخ تاریخی همان نماد + سبد کیفیت، با هموارسازی لاپلاس
 *
 * این فایل هیچ وابستگی‌ای به React یا KLineCharts ندارد.
 */

import type {
  Candle,
  DoubleTapPattern,
  FormationConfidence,
  FormationEstimate,
} from './types';
import { isPivotHigh, isPivotLow } from './patterns/pivots';

export interface EngineCandle {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export interface DoubleTapParams {
  pivLeft: number;
  pivRight: number;
  tolAtr: number;
  minSpan: number;
  maxSpan: number;
  minHeightAtr: number;
  requireTrendContext: boolean;
  nonOverlapBars: number;
  atrPeriod: number;
  profile?: 'source' | 'precision';
}

/** پارامترهای اعلام‌شده در سورس تلگرام؛ برای مقایسه حفظ می‌شوند. */
export const DEFAULT_SOURCE_PARAMS: DoubleTapParams = {
  pivLeft: 6,
  pivRight: 4,
  tolAtr: 0.85,
  minSpan: 3,
  maxSpan: 120,
  minHeightAtr: 1.0,
  requireTrendContext: false,
  nonOverlapBars: 0,
  atrPeriod: 14,
  profile: 'source',
};

/** پیش‌فرض محصول برای «دقت بیشتر»؛ اثرش باید روی دادهٔ واقعی سنجیده شود. */
export const DEFAULT_PRECISION_PARAMS: DoubleTapParams = {
  pivLeft: 5,
  pivRight: 4,
  tolAtr: 0.45,
  minSpan: 5,
  maxSpan: 80,
  minHeightAtr: 1.0,
  requireTrendContext: true,
  nonOverlapBars: 10,
  atrPeriod: 14,
  profile: 'precision',
};

type Point = { index: number; price: number; timestamp: number };

export function calculateAtr(candles: readonly EngineCandle[], period = 14): number[] {
  const n = candles.length;
  const tr = new Array<number>(n).fill(0);
  for (let i = 0; i < n; i++) {
    const prevClose = i > 0 ? candles[i - 1].close : candles[i].close;
    tr[i] = Math.max(
      candles[i].high - candles[i].low,
      Math.abs(candles[i].high - prevClose),
      Math.abs(candles[i].low - prevClose)
    );
  }
  const atr = new Array<number>(n).fill(0);
  let sum = 0;
  for (let i = 0; i < n; i++) {
    sum += tr[i];
    if (i >= period) sum -= tr[i - period];
    atr[i] = i >= period - 1 ? sum / period : sum / (i + 1);
  }
  return atr;
}

function qualityScore(args: {
  diff: number;
  tol: number;
  height: number;
  atr: number;
  span: number;
  trendContext: boolean;
  hasOrigin: boolean;
  status: DoubleTapPattern['status'];
}): number {
  const peakEquality = 1 - Math.min(1, args.diff / Math.max(args.tol, 1e-9));
  const depth = Math.min(1, args.height / Math.max(args.atr * 2, 1e-9));
  const spanBalance = 1 - Math.min(1, Math.abs(args.span - 20) / 40);
  const trend = args.trendContext ? 1 : args.hasOrigin ? 0.5 : 0.25;
  const breakout =
    args.status === 'active' || args.status === 'tp1_hit' || args.status === 'tp2_hit'
      ? 1
      : args.status === 'forming'
        ? 0.5
        : 0;
  return Math.round(
    40 * peakEquality + 20 * depth + 15 * spanBalance + 15 * trend + 10 * breakout
  );
}

function buildPattern(
  data: readonly EngineCandle[],
  atr: number[],
  type: DoubleTapPattern['type'],
  p1: Point,
  p2: Point,
  params: DoubleTapParams
): DoubleTapPattern | null {
  const isTop = type === 'DOUBLE_TOP';
  const span = p2.index - p1.index;
  if (span < params.minSpan || span > params.maxSpan) return null;

  const currentAtr = atr[p2.index] || atr[data.length - 1] || 1;
  const diff = Math.abs(p1.price - p2.price);
  const tol = params.tolAtr * currentAtr;
  if (diff > tol) return null;

  let neckPrice = isTop ? Infinity : -Infinity;
  let neckIdx = -1;
  for (let k = p1.index + 1; k < p2.index; k++) {
    if (isTop) {
      if (data[k].low < neckPrice) {
        neckPrice = data[k].low;
        neckIdx = k;
      }
    } else if (data[k].high > neckPrice) {
      neckPrice = data[k].high;
      neckIdx = k;
    }
  }
  if (neckIdx === -1 || !Number.isFinite(neckPrice)) return null;

  const height = isTop ? Math.max(p1.price, p2.price) - neckPrice : neckPrice - Math.min(p1.price, p2.price);
  if (height < params.minHeightAtr * currentAtr) return null;

  const target1 = isTop ? neckPrice - height : neckPrice + height;
  const target2 = isTop ? neckPrice - 1.618 * height : neckPrice + 1.618 * height;
  const stopLoss = isTop
    ? Math.max(p1.price, p2.price) + 0.25 * currentAtr
    : Math.min(p1.price, p2.price) - 0.25 * currentAtr;

  // نقطهٔ آغاز حرکت (لگ قبل از قله/کف اول) برای زمینهٔ روند و ترسیم.
  let origin: Point | undefined;
  const originStart = Math.max(0, p1.index - span);
  if (isTop) {
    let low = Infinity;
    let idx = -1;
    for (let k = originStart; k < p1.index; k++) {
      if (data[k].low < low) {
        low = data[k].low;
        idx = k;
      }
    }
    if (idx !== -1 && Number.isFinite(low)) origin = { index: idx, price: low, timestamp: data[idx].timestamp };
  } else {
    let high = -Infinity;
    let idx = -1;
    for (let k = originStart; k < p1.index; k++) {
      if (data[k].high > high) {
        high = data[k].high;
        idx = k;
      }
    }
    if (idx !== -1 && Number.isFinite(high)) origin = { index: idx, price: high, timestamp: data[idx].timestamp };
  }

  const trendContext = origin
    ? isTop
      ? origin.price <= Math.min(p1.price, p2.price) - currentAtr
      : origin.price >= Math.max(p1.price, p2.price) + currentAtr
    : false;

  const invalidation = isTop
    ? Math.max(p1.price, p2.price) + 0.5 * currentAtr
    : Math.min(p1.price, p2.price) - 0.5 * currentAtr;

  let breakoutIdx = -1;
  let invalidatedIdx = -1;
  for (let b = p2.index + 1; b < data.length; b++) {
    const close = data[b].close;
    const broke = isTop ? close < neckPrice : close > neckPrice;
    const invalid = isTop ? close > invalidation : close < invalidation;
    if (broke) {
      breakoutIdx = b;
      break;
    }
    if (invalid) {
      invalidatedIdx = b;
      break;
    }
  }

  let status: DoubleTapPattern['status'] = 'forming';
  if (breakoutIdx !== -1) {
    const tp1Hit = data
      .slice(breakoutIdx + 1)
      .some((c) => (isTop ? c.low <= target1 : c.high >= target1));
    const tp2Hit = data
      .slice(breakoutIdx + 1)
      .some((c) => (isTop ? c.low <= target2 : c.high >= target2));
    status = tp2Hit ? 'tp2_hit' : tp1Hit ? 'tp1_hit' : 'active';
  } else if (invalidatedIdx !== -1) {
    status = 'invalidated';
  }

  const retestIdx =
    breakoutIdx !== -1
      ? breakoutIdx
      : Math.min(data.length - 1, p2.index + Math.max(1, Math.round(span / 2)));
  const retestPrice = breakoutIdx !== -1 ? neckPrice : (p2.price + neckPrice) / 2;

  const quality = qualityScore({
    diff,
    tol,
    height,
    atr: currentAtr,
    span,
    trendContext,
    hasOrigin: Boolean(origin),
    status,
  });

  return {
    id: `${type === 'DOUBLE_TOP' ? 'double-top' : 'double-bottom'}-${p1.index}-${p2.index}`,
    type,
    origin,
    peak1: p1,
    neckline: { index: neckIdx, price: neckPrice, timestamp: data[neckIdx].timestamp },
    peak2: p2,
    retest: {
      index: retestIdx,
      price: retestPrice,
      timestamp: data[retestIdx]?.timestamp ?? p2.timestamp,
    },
    breakoutIndex: breakoutIdx !== -1 ? breakoutIdx : undefined,
    breakoutTs: breakoutIdx !== -1 ? data[breakoutIdx].timestamp : undefined,
    target1,
    target2,
    stopLoss,
    score: quality,
    quality,
    height,
    status,
    trendContext,
    profile: params.profile ?? 'precision',
  };
}

function suppressOverlaps(patterns: DoubleTapPattern[], nonOverlapBars: number): DoubleTapPattern[] {
  const sorted = [...patterns].sort((a, b) => a.peak2.index - b.peak2.index);
  const kept: DoubleTapPattern[] = [];
  for (const pattern of sorted) {
    const conflict = kept.find(
      (k) =>
        k.type === pattern.type &&
        (k.peak1.index === pattern.peak1.index ||
          k.peak2.index === pattern.peak2.index ||
          Math.abs(k.peak2.index - pattern.peak2.index) <= nonOverlapBars)
    );
    if (!conflict) {
      kept.push(pattern);
    } else if (pattern.quality > conflict.quality) {
      kept[kept.indexOf(conflict)] = pattern;
    }
  }
  return kept.sort((a, b) => a.peak2.index - b.peak2.index);
}

export function detectDoubleTapPatterns(
  candles: readonly EngineCandle[],
  params: Partial<DoubleTapParams> = {}
): DoubleTapPattern[] {
  const p: DoubleTapParams = { ...DEFAULT_PRECISION_PARAMS, ...params };
  const data = candles;
  const n = data.length;
  if (n < Math.max(20, p.atrPeriod + 2)) return [];

  const atr = calculateAtr(data, p.atrPeriod);
  const highs: Point[] = [];
  const lows: Point[] = [];

  for (let i = p.pivLeft; i < n - p.pivRight; i++) {
    if (isPivotHigh(data, i, p.pivLeft, p.pivRight)) {
      highs.push({ index: i, price: data[i].high, timestamp: data[i].timestamp });
    }
    if (isPivotLow(data, i, p.pivLeft, p.pivRight)) {
      lows.push({ index: i, price: data[i].low, timestamp: data[i].timestamp });
    }
  }

  const patterns: DoubleTapPattern[] = [];
  for (let i = 0; i < highs.length - 1; i++) {
    const pattern = buildPattern(data, atr, 'DOUBLE_TOP', highs[i], highs[i + 1], p);
    if (pattern) patterns.push(pattern);
  }
  for (let i = 0; i < lows.length - 1; i++) {
    const pattern = buildPattern(data, atr, 'DOUBLE_BOTTOM', lows[i], lows[i + 1], p);
    if (pattern) patterns.push(pattern);
  }

  return suppressOverlaps(patterns, p.nonOverlapBars);
}

/** نرخ لاپلاس: (موفق + ۱) / (کل + ۲) — عدد ساختگی ۰/۱۰۰ نمی‌دهد. */
export function laplaceRate(successes: number, failures: number): number {
  const resolved = successes + failures;
  return (successes + 1) / (resolved + 2);
}

/** بازهٔ ویلسون ۸۰٪ برای نمایش عدم‌قطعیت. */
export function wilsonInterval(successes: number, resolved: number, z = 1.2816): [number, number] {
  if (resolved <= 0) return [0, 1];
  const p = successes / resolved;
  const denom = 1 + (z * z) / resolved;
  const center = (p + (z * z) / (2 * resolved)) / denom;
  const margin =
    (z * Math.sqrt((p * (1 - p)) / resolved + (z * z) / (4 * resolved * resolved))) / denom;
  return [Math.max(0, center - margin), Math.min(1, center + margin)];
}

function confidenceFor(resolved: number): FormationConfidence {
  if (resolved < 8) return 'none';
  if (resolved < 20) return 'low';
  if (resolved < 50) return 'medium';
  return 'high';
}

export function patternOutcome(
  pattern: DoubleTapPattern,
  candles: readonly EngineCandle[],
  atr: number,
  horizon: number
): 'success' | 'failure' | 'unresolved' {
  const isTop = pattern.type === 'DOUBLE_TOP';
  const start = pattern.peak2.index + 1;
  const end = Math.min(candles.length, start + horizon);
  const invalidation = isTop
    ? Math.max(pattern.peak1.price, pattern.peak2.price) + 0.5 * atr
    : Math.min(pattern.peak1.price, pattern.peak2.price) - 0.5 * atr;

  for (let i = start; i < end; i++) {
    const close = candles[i].close;
    if (isTop ? close > invalidation : close < invalidation) return 'failure';
    if (isTop ? close < pattern.neckline.price : close > pattern.neckline.price) return 'success';
  }
  return 'unresolved';
}

function bucketOf(quality: number, thresholds: [number, number]): number {
  if (quality <= thresholds[0]) return 0;
  if (quality <= thresholds[1]) return 1;
  return 2;
}

export interface CohortEstimate {
  successes: number;
  failures: number;
  resolved: number;
  band?: number;
  label?: string;
}

export function estimateFormation(
  patterns: readonly DoubleTapPattern[],
  candles: readonly EngineCandle[],
  atr: number,
  currentId: string,
  horizon = 10,
  cohort?: CohortEstimate
): FormationEstimate | null {
  const current = patterns.find((p) => p.id === currentId);
  if (!current || current.status !== 'forming') return null;

  const samples = patterns.filter(
    (p) => p.id !== currentId && p.peak2.index + 1 < candles.length
  );
  const resolvedSamples: Array<{ pattern: DoubleTapPattern; outcome: 'success' | 'failure' }> = [];
  for (const sample of samples) {
    const outcome = patternOutcome(sample, candles, atr, horizon);
    if (outcome !== 'unresolved') resolvedSamples.push({ pattern: sample, outcome });
  }

  let successes = resolvedSamples.filter((s) => s.outcome === 'success').length;
  let failures = resolvedSamples.filter((s) => s.outcome === 'failure').length;
  let qualityBucket: number | undefined;

  // سبد کیفیت: اگر همان tercile حداقل ۸ نمونه دارد، نرخ همان سبد نمایش داده می‌شود.
  const qualities = samples.map((s) => s.quality).sort((a, b) => a - b);
  if (qualities.length >= 8) {
    const thresholds: [number, number] = [
      qualities[Math.floor(qualities.length / 3)],
      qualities[Math.floor((2 * qualities.length) / 3)],
    ];
    qualityBucket = bucketOf(current.quality, thresholds);
    const bucketSamples = resolvedSamples.filter(
      (s) => bucketOf(s.pattern.quality, thresholds) === qualityBucket
    );
    if (bucketSamples.length >= 8) {
      successes = bucketSamples.filter((s) => s.outcome === 'success').length;
      failures = bucketSamples.filter((s) => s.outcome === 'failure').length;
    }
  }

  let method: FormationEstimate['method'] = 'same-symbol';
  // fallback کوهورت بازار فقط وقتی نمونهٔ همان نماد کم است.
  if (successes + failures < 8 && cohort && cohort.resolved >= 8) {
    successes = cohort.successes;
    failures = cohort.failures;
    method = 'market-cohort';
    qualityBucket = cohort.band;
  }

  const resolved = successes + failures;
  const confidence = confidenceFor(resolved);
  const probability = resolved >= 8 ? laplaceRate(successes, failures) : null;
  const [intervalLow, intervalHigh] = resolved > 0 ? wilsonInterval(successes, resolved) : [undefined, undefined];

  return {
    probability,
    successes,
    failures,
    resolved,
    confidence,
    horizon,
    method,
    qualityBucket,
    intervalLow,
    intervalHigh,
  };
}

/** آخرین الگو از نظر زمان بازار؛ فقط اگر در حال تشکیل باشد، واجد درصد است. */
export function selectLastFormingPattern(
  patterns: readonly DoubleTapPattern[]
): DoubleTapPattern | null {
  if (patterns.length === 0) return null;
  const last = [...patterns].sort((a, b) => b.peak2.index - a.peak2.index)[0];
  return last.status === 'forming' ? last : null;
}

/** سازگاری با مصرف‌کننده‌هایی که Candle مدل را می‌دهند. */
export type { Candle };
