/**
 * model/events/zone.ts
 *
 * پورت p21 — «S/R Retest Breakout» (Indi 248، MPL-2.0، @IndicatorsforTV):
 * - زون دو سوئینگی از `pivotLen=7`؛ تلورانس برابری = stdev(close, 40) × 1.0
 * - ضخامت زون از o/h/l/c هر دو کندل پیوت (فقط مقادیر در سمت زون و داخل تلورانس)
 * - رد زونِ هم‌پوشان در قیمت و زمان
 * - ماشین حالت 0 → ±1 → ±2 → ±3؛ شکست ناموفق برمی‌گردد؛ expiry ۵۰۰ کندل؛ حداکثر ۱۵۰ زون
 * - حجم پایین‌تایم‌فریم در دسترس نیست ⇒ `volumeBalanceAvailable:false` و پروکسی جهت کندل
 *
 * تابع خالص است؛ نه React، نه KLineCharts.
 */
import type { EngineCandle } from '../doubleTapEngine';
import { findAlternatingPivots, type PivotPoint } from '../patterns/pivots';
import type { EventConfig } from './config';

export type SrRetestConfig = EventConfig['srRetest'];

export interface SrRetestZone {
  upper: number;
  lower: number;
  fromIndex: number;
  toIndex: number;
  /** 0 بی‌طرف · ±1 شکست تمام‌کندلی · ±2 بستهٔ عبور · ±3 ریتست تثبیت‌شده */
  state: 0 | 1 | 2 | 3 | -1 | -2 | -3;
  /** حجم خرید/فروش پایین‌تایم‌فریم در وب موجود نیست؛ همیشه false. */
  volumeBalanceAvailable: false;
  breakoutIndex?: number;
  retestIndex?: number;
  direction: 'bullish' | 'bearish';
}

interface WorkingZone extends SrRetestZone {
  /** کندل تأیید سوئینگ دوم؛ ماشین حالت از این‌جا شروع می‌شود. */
  createdIndex: number;
  side: 'support' | 'resistance';
}

function stdevSeries(closes: readonly number[], length: number): number[] {
  const out = new Array<number>(closes.length).fill(0);
  let sum = 0;
  let sumSq = 0;
  for (let i = 0; i < closes.length; i++) {
    const value = closes[i];
    sum += value;
    sumSq += value * value;
    if (i >= length) {
      const old = closes[i - length];
      sum -= old;
      sumSq -= old * old;
    }
    if (i >= length - 1) {
      const mean = sum / length;
      out[i] = Math.sqrt(Math.max(0, sumSq / length - mean * mean));
    }
  }
  return out;
}

/** p21 `zoneBounds`: لبه از max/min سوئینگ‌ها و ضخامت از o/h/l/c. */
function zoneBounds(
  p1: PivotPoint,
  p2: PivotPoint,
  candles: readonly EngineCandle[],
  resistance: boolean,
  tolerance: number,
): { upper: number; lower: number } {
  const bar1 = candles[p1.index];
  const bar2 = candles[p2.index];
  const edge = resistance
    ? Math.max(bar1.high, bar2.high)
    : Math.min(bar1.low, bar2.low);
  let maxDistance = 0;
  for (const bar of [bar1, bar2]) {
    for (const value of [bar.open, bar.high, bar.low, bar.close]) {
      const distance = resistance ? edge - value : value - edge;
      if (distance >= 0 && distance <= tolerance) maxDistance = Math.max(maxDistance, distance);
    }
  }
  const thickness = Math.max(maxDistance, 0.01);
  return resistance
    ? { upper: edge, lower: edge - thickness }
    : { upper: edge + thickness, lower: edge };
}

function overlaps(
  candidate: { fromIndex: number; upper: number; lower: number },
  existing: WorkingZone,
  lastIndex: number,
): boolean {
  const timeOverlap = candidate.fromIndex <= lastIndex && lastIndex >= existing.fromIndex;
  const priceOverlap = candidate.lower <= existing.upper && candidate.upper >= existing.lower;
  return timeOverlap && priceOverlap;
}

function runStateMachine(
  zone: WorkingZone,
  candles: readonly EngineCandle[],
  lastIndex: number,
): void {
  let state: SrRetestZone['state'] = 0;
  let breakBar: number | null = null;
  let retestIndex: number | undefined;
  for (let i = zone.createdIndex + 1; i <= lastIndex; i++) {
    const bar = candles[i];
    const wholeBelow = bar.high < zone.lower;
    const wholeAbove = bar.low > zone.upper;
    const closeAbove = bar.close > zone.upper;
    const closeBelow = bar.close < zone.lower;
    const touched = bar.high >= zone.lower && bar.low <= zone.upper;

    if (state === 0) {
      if (wholeBelow) state = -1;
      else if (wholeAbove) state = 1;
    } else if (state === -1) {
      if (closeAbove) {
        state = 2;
        breakBar = i;
      } else if (wholeAbove) {
        state = 1;
        breakBar = null;
      }
    } else if (state === 1) {
      if (closeBelow) {
        state = -2;
        breakBar = i;
      } else if (wholeBelow) {
        state = -1;
        breakBar = null;
      }
    } else if (state === 2) {
      if (breakBar != null && i > breakBar && touched && bar.close >= zone.lower) {
        state = 3;
        retestIndex = i;
        break;
      }
      if (closeBelow) {
        // شکست ناموفق: بستهٔ بازگشتی داخل/زیر زون.
        state = wholeBelow ? -1 : 0;
        breakBar = null;
      }
    } else if (state === -2) {
      if (breakBar != null && i > breakBar && touched && bar.close <= zone.upper) {
        state = -3;
        retestIndex = i;
        break;
      }
      if (closeAbove) {
        state = wholeAbove ? 1 : 0;
        breakBar = null;
      }
    }
    // ±3 یخ‌زده است.
  }

  zone.state = state;
  zone.breakoutIndex = breakBar ?? undefined;
  zone.retestIndex = retestIndex;
  if (state === 3) zone.direction = 'bullish';
  else if (state === -3) zone.direction = 'bearish';
  else zone.direction = zone.side === 'support' ? 'bullish' : 'bearish';
}

export function detectSrRetest(
  candles: readonly EngineCandle[],
  config: SrRetestConfig,
  offset = 0,
): SrRetestZone[] {
  const n = candles.length;
  const lastIndex = n - 1;
  if (n < config.pivotLen * 2 + config.stdevLen) return [];

  const stdev = stdevSeries(candles.map((c) => c.close), config.stdevLen);
  const pivots = findAlternatingPivots(candles, config.pivotLen, config.pivotLen).filter(
    (pivot) => pivot.index + config.pivotLen <= lastIndex,
  );
  if (pivots.length < 2) return [];

  const zones: WorkingZone[] = [];
  let previousHigh: PivotPoint | null = null;
  let previousLow: PivotPoint | null = null;

  const tryCreate = (first: PivotPoint, second: PivotPoint, side: 'support' | 'resistance') => {
    const createdIndex = Math.min(lastIndex, second.index + config.pivotLen);
    const tolerance = (stdev[createdIndex] ?? 0) * config.toleranceStdevMult;
    if (Math.abs(second.price - first.price) > tolerance) return;
    const bounds = zoneBounds(first, second, candles, side === 'resistance', tolerance);
    const fromIndex = Math.min(first.index, second.index);
    if (!(bounds.upper > bounds.lower)) return;
    const candidate = { fromIndex, upper: bounds.upper, lower: bounds.lower };
    if (zones.some((zone) => overlaps(candidate, zone, lastIndex))) return;
    zones.push({
      upper: bounds.upper,
      lower: bounds.lower,
      fromIndex,
      toIndex: lastIndex,
      state: 0,
      volumeBalanceAvailable: false,
      direction: side === 'support' ? 'bullish' : 'bearish',
      createdIndex,
      side,
    });
  };

  for (const pivot of pivots) {
    if (pivot.kind === 'high') {
      if (previousHigh) tryCreate(previousHigh, pivot, 'resistance');
      previousHigh = pivot;
    } else {
      if (previousLow) tryCreate(previousLow, pivot, 'support');
      previousLow = pivot;
    }
  }

  // expiry: زونِ قدیمی‌تر از expiryBars حذف می‌شود؛ سقف تعداد هم از جدیدها نگه می‌دارد.
  const liveZones = zones
    .filter((zone) => lastIndex - zone.fromIndex <= config.expiryBars)
    .sort((a, b) => a.fromIndex - b.fromIndex)
    .slice(-config.maxZones);

  for (const zone of liveZones) runStateMachine(zone, candles, lastIndex);

  return liveZones.map((zone) => ({
    upper: zone.upper,
    lower: zone.lower,
    fromIndex: zone.fromIndex,
    toIndex: zone.toIndex,
    state: zone.state,
    volumeBalanceAvailable: false,
    breakoutIndex: zone.breakoutIndex,
    retestIndex: zone.retestIndex,
    direction: zone.direction,
  }));
}
