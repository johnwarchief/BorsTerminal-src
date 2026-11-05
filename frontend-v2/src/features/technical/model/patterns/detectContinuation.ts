// model/patterns/detectContinuation.ts
import type { EngineCandle } from '../doubleTapEngine';
import type { PatternConfig } from './config';
import type { BoundaryLine, ChartPattern, PatternKind, PatternPoint } from './types';
import { findAlternatingPivots, type PivotPoint } from './pivots';
import { emitPattern, lineSlope, lineValue, toPoint, touchCount } from './geometry';

/** وزن‌های امتیاز کیفیت؛ امتیازدهی‌اند نه دروازهٔ تحلیلی، پس در PATTERN_CONFIG نمی‌نشینند. */
const QUALITY_BASE = 50;
const QUALITY_WIDTH_WEIGHT = 25;
const QUALITY_TOUCH_WEIGHT = 25;
const QUALITY_TOUCH_FULL = 6;
const PENNANT_QUALITY_PENALTY = 5;
const TRIANGLE_QUALITY = 65;
const SYMMETRIC_QUALITY = 60;
const RECTANGLE_QUALITY = 55;
const WEDGE_QUALITY = 55;

const clampQuality = (value: number) => Math.max(0, Math.min(100, value));

function lastTwo(pivots: PivotPoint[], kind: 'high' | 'low'): [PivotPoint, PivotPoint] | null {
  const items = pivots.filter((p) => p.kind === kind);
  if (items.length < 2) return null;
  return [items[items.length - 2]!, items[items.length - 1]!];
}

function lines(highs: [PivotPoint, PivotPoint], lows: [PivotPoint, PivotPoint], candles: readonly EngineCandle[]) {
  return {
    upper: { from: toPoint(highs[0], candles), to: toPoint(highs[1], candles) } as BoundaryLine,
    lower: { from: toPoint(lows[0], candles), to: toPoint(lows[1], candles) } as BoundaryLine,
  };
}

/**
 * نقاط باید صعودی باشند: emitPattern لنگر را آخرین نقطه می‌گیرد، و آرایهٔ بریف
 * می‌تواند با lows[1] تمام شود حتی وقتی highs[1] دیرتر است. بدون این مرتب‌سازی
 * اسکن شکست از پیوتی شروع می‌شود که هنوز در آیندهٔ لنگر ساخته نشده (look-ahead).
 */
function sortPoints(points: PatternPoint[]): PatternPoint[] {
  return [...points].sort((a, b) => a.index - b.index);
}

/** R-PAT-14: امضای جفت پیوت مرزی (highs[1], lows[1]) برای حذف هم‌پوشانی بین خانواده‌ها. */
function boundaryFingerprint(highs: [PivotPoint, PivotPoint], lows: [PivotPoint, PivotPoint]): string {
  return `${highs[1].index}:${lows[1].index}`;
}

/** خروجی: الگوهای ادامه‌دهندهٔ باز/تأییدشده؛ الگوهای منقضی در emitPattern حذف می‌شوند. */
export function detectContinuation(
  candles: readonly EngineCandle[],
  atr: number,
  config: PatternConfig,
): ChartPattern[] {
  if (!Number.isFinite(atr) || atr <= 0) return [];
  const pivots = findAlternatingPivots(candles, config.pivLeft, config.pivRight);
  const out: ChartPattern[] = [];
  /** R-PAT-14: جفت‌های مرزی‌ای که پرچم/پنانت برایشان منتشر شده است. */
  const continuationPairs = new Set<string>();

  for (let i = 0; i + 3 < pivots.length; i++) {
    const legStart = pivots[i]!;
    const legEnd = pivots[i + 1]!;
    if (legStart.kind === legEnd.kind) continue;
    const bullish = legStart.kind === 'low';
    const legHeight = Math.abs(legEnd.price - legStart.price);
    const legBars = legEnd.index - legStart.index;
    // R-PAT-9: هر خانواده دروازهٔ قدرت لگ خودش را دارد.
    const flagImpulse = legHeight >= config.flag.impulseLegAtrMin * atr;
    const pennantImpulse = legHeight >= config.pennant.impulseLegAtrMin * atr;
    if (legBars < config.flag.minLegBars || (!flagImpulse && !pennantImpulse)) continue;

    const after = pivots.filter(
      (p) => p.index > legEnd.index
        && p.index <= legEnd.index + Math.max(config.flag.maxBars, config.pennant.maxBars),
    );
    const highs = lastTwo(after, 'high');
    const lows = lastTwo(after, 'low');
    if (!highs || !lows) continue;
    const { upper, lower } = lines(highs, lows, candles);
    const widthAtEnd = Math.abs(lineValue(upper, legEnd.index) - lineValue(lower, legEnd.index));
    if (widthAtEnd <= 0) continue;

    const touches = touchCount(after, upper, 'high', atr * config.touchToleranceAtr)
      + touchCount(after, lower, 'low', atr * config.touchToleranceAtr);
    if (touches < config.minTouchesPerLine * 2) continue;

    const points = sortPoints([
      toPoint(legStart, candles), toPoint(legEnd, candles),
      toPoint(highs[0], candles), toPoint(highs[1], candles),
      toPoint(lows[0], candles), toPoint(lows[1], candles),
    ]);
    const target = bullish ? legEnd.price + legHeight : legEnd.price - legHeight;
    const stopLoss = bullish ? legEnd.price - legHeight : legEnd.price + legHeight;
    const quality = clampQuality(
      QUALITY_BASE
      + QUALITY_WIDTH_WEIGHT
        * (1 - Math.min(1, widthAtEnd / (legHeight * (config.flag.channelMaxWidthPct / 100))))
      + QUALITY_TOUCH_WEIGHT * Math.min(1, touches / QUALITY_TOUCH_FULL),
    );

    if (flagImpulse && widthAtEnd <= (config.flag.channelMaxWidthPct / 100) * legHeight) {
      const slope = lineSlope(upper);
      const slopeAgainst = config.flag.slopeOpposite
        && ((bullish && slope > 0) || (!bullish && slope < 0));
      if (!slopeAgainst) {
        const flag = emitPattern({
          kind: bullish ? 'FLAG_BULL' : 'FLAG_BEAR',
          direction: bullish ? 'bullish' : 'bearish',
          family: 'continuation',
          points, upper, lower, target, stopLoss, quality,
          // R-PAT-5: پنجرهٔ انقضای خانوادهٔ پرچم.
          maxBars: config.flag.maxBars,
        }, candles, config);
        if (flag) {
          out.push(flag);
          continuationPairs.add(boundaryFingerprint(highs, lows));
        }
      }
    }

    // پنانت: همان لگ، ولی دو خط همگرا (سقف پایین‌آینده و کف بالارونده).
    // عرض در شروع و پایان خودِ فشرده‌سازی سنجیده می‌شود؛ فرمول بریف عرض را در
    // legEnd (پیش از شروع فشرده‌سازی) می‌گرفت که برای خطوط همگرا هرگز کوچک نمی‌شود.
    const consolidationStart = Math.min(highs[0]!.index, lows[0]!.index);
    const consolidationEnd = Math.max(highs[1]!.index, lows[1]!.index);
    const widthAtStart = Math.abs(lineValue(upper, consolidationStart) - lineValue(lower, consolidationStart));
    const widthAtConsolidationEnd = Math.abs(lineValue(upper, consolidationEnd) - lineValue(lower, consolidationEnd));
    const converge = widthAtStart > 0
      && widthAtConsolidationEnd <= (1 - config.pennant.convergenceMin) * widthAtStart;
    if (pennantImpulse && converge && legBars <= config.pennant.maxBars) {
      const pennant = emitPattern({
        kind: 'PENNANT',
        direction: bullish ? 'bullish' : 'bearish',
        family: 'continuation',
        points, upper, lower, target, stopLoss,
        quality: quality - PENNANT_QUALITY_PENALTY,
        maxBars: config.pennant.maxBars,
      }, candles, config);
      if (pennant) {
        out.push(pennant);
        continuationPairs.add(boundaryFingerprint(highs, lows));
      }
    }
  }

  out.push(...detectTriangleFamily(pivots, candles, atr, config, continuationPairs));
  return dedupe(out);
}

function detectTriangleFamily(
  pivots: PivotPoint[],
  candles: readonly EngineCandle[],
  atr: number,
  config: PatternConfig,
  continuationPairs: ReadonlySet<string>,
): ChartPattern[] {
  const highs = lastTwo(pivots, 'high');
  const lows = lastTwo(pivots, 'low');
  if (!highs || !lows) return [];
  // R-PAT-14: اگر پرچم/پنانت همین جفت پیوت مرزی را مصرف کرده، مثلث/مستطیل/گُوه تکراری است.
  if (continuationPairs.has(boundaryFingerprint(highs, lows))) return [];

  const { upper, lower } = lines(highs, lows, candles);
  const h1 = highs[0]!.price, h2 = highs[1]!.price;
  const l1 = lows[0]!.price, l2 = lows[1]!.price;
  const flat = config.triangle.flatToleranceAtr * atr;
  const span = Math.abs(highs[1]!.index - lows[1]!.index);
  if (span < config.triangle.minSpan) return [];
  // R-PAT-5: انقضا با پنجرهٔ هر خانواده در emitPattern اعمال می‌شود؛ گارد عرضی مثلث لازم نیست.

  const startIndex = Math.min(highs[0]!.index, lows[0]!.index);
  const endIndex = Math.max(highs[1]!.index, lows[1]!.index);
  const widthStart = Math.abs(lineValue(upper, startIndex) - lineValue(lower, startIndex));
  const widthEnd = Math.abs(lineValue(upper, endIndex) - lineValue(lower, endIndex));
  const converging = widthStart > 0
    && widthEnd <= (1 - config.triangle.convergenceMin) * widthStart;
  // R-PAT-9: گُوه آستانهٔ همگرایی خودش را دارد، نه آستانهٔ مثلث.
  const wedgeConverging = widthStart > 0
    && widthEnd <= (1 - config.wedge.convergenceMin) * widthStart;

  const points = sortPoints([
    toPoint(highs[0], candles), toPoint(lows[0], candles),
    toPoint(highs[1], candles), toPoint(lows[1], candles),
  ]);
  const height = Math.abs(h1 - l1);
  const upperEnd = lineValue(upper, endIndex);
  const lowerEnd = lineValue(lower, endIndex);
  // R-PAT-15: هدف/حد ضرر آینه‌ای بر اساس مرزها؛ خنثی (مستطیل/متقارن) پیش‌فرض صعودی را نگه می‌دارد.
  const targets = (direction: ChartPattern['direction']) => (direction === 'bearish'
    ? { target: lowerEnd - height, stopLoss: upperEnd + atr }
    : { target: upperEnd + height, stopLoss: lowerEnd - atr });
  const base = { points, upper, lower, family: 'continuation' as const };

  const out: ChartPattern[] = [];
  const push = (kind: PatternKind, direction: ChartPattern['direction'], quality: number, maxBars: number) => {
    const emitted = emitPattern(
      { ...base, ...targets(direction), kind, direction, quality, maxBars },
      candles,
      config,
    );
    if (emitted) out.push(emitted);
  };

  if (Math.abs(h2 - h1) <= flat && l2 > l1) push('TRIANGLE_ASC', 'bullish', TRIANGLE_QUALITY, config.triangle.maxBars);
  if (Math.abs(l2 - l1) <= flat && h2 < h1) push('TRIANGLE_DESC', 'bearish', TRIANGLE_QUALITY, config.triangle.maxBars);
  if (converging && h2 < h1 && l2 > l1) push('TRIANGLE_SYM', 'neutral', SYMMETRIC_QUALITY, config.triangle.maxBars);
  if (Math.abs(h2 - h1) <= config.rectangle.flatToleranceAtr * atr
    && Math.abs(l2 - l1) <= config.rectangle.flatToleranceAtr * atr) {
    // R-PAT-5: پنجرهٔ انقضای مستطیل، نه پنجرهٔ مثلث.
    push('RECTANGLE', 'neutral', RECTANGLE_QUALITY, config.rectangle.maxBars);
  }
  if (wedgeConverging && h2 > h1 && l2 > l1) push('WEDGE_RISING', 'bearish', WEDGE_QUALITY, config.wedge.maxBars);
  if (wedgeConverging && h2 < h1 && l2 < l1) push('WEDGE_FALLING', 'bullish', WEDGE_QUALITY, config.wedge.maxBars);
  return out;
}

function dedupe(patterns: ChartPattern[]): ChartPattern[] {
  const seen = new Set<string>();
  return patterns.filter((p) => (seen.has(p.id) ? false : (seen.add(p.id), true)));
}
