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

/**
 * هم‌پوشانیِ بازهٔ فشرده‌سازی: دو پنجره‌ای که بخشی از یک فشرده‌سازی را شریک‌اند
 * یک شکل نیستند. فقط اشتراکِ داخلی ملاک است؛ پنجره‌های مجاورِ یک‌سر مشترک تکرار نیستند.
 */
function overlaps(a: [number, number], b: [number, number]): boolean {
  return a[0] < b[1] && b[0] < a[1];
}

/**
 * اکستریم واقعی کندل‌ها در پنجرهٔ فشرده‌سازی. خطوط مرزی از دو پیوت ساخته می‌شوند
 * و اکستریمِ میانی/پایانی را نشان نمی‌دهند؛ دروازهٔ عمق باید روی کندل سنجیده شود.
 */
function windowExtremes(
  candles: readonly EngineCandle[],
  from: number,
  to: number,
): { high: number; low: number } {
  let high = -Infinity;
  let low = Infinity;
  const start = Math.max(0, from);
  const end = Math.min(candles.length - 1, to);
  for (let i = start; i <= end; i++) {
    high = Math.max(high, candles[i]!.high);
    low = Math.min(low, candles[i]!.low);
  }
  return { high, low };
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
  /** R-PAT-14: جفت‌های مرزی‌ای که هر الگویی (پرچم/پنانت/مثلث/مستطیل/گُوه) برایشان منتشر شده است. */
  const usedPairs = new Set<string>();
  /** بازهٔ فشرده‌سازیِ شکل‌های منتشرشده؛ پنجرهٔ تازه نباید همان فشرده‌سازی را بازتوصیف کند. */
  const usedSpans: Array<[number, number]> = [];
  const remember = (fingerprint: string, span: [number, number]) => {
    usedPairs.add(fingerprint);
    usedSpans.push(span);
  };
  const invalidationBuffer = config.invalidationBufferAtr * atr;

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
    const fingerprint = boundaryFingerprint(highs, lows);
    const consolidationStart = Math.min(highs[0]!.index, lows[0]!.index);
    const consolidationEnd = Math.max(highs[1]!.index, lows[1]!.index);
    const span: [number, number] = [consolidationStart, consolidationEnd];
    const widthAtConsolidationStart = Math.abs(
      lineValue(upper, consolidationStart) - lineValue(lower, consolidationStart));
    const widthAtConsolidationEnd = Math.abs(
      lineValue(upper, consolidationEnd) - lineValue(lower, consolidationEnd));
    // The pole ends at the furthest point price actually reached before the
    // consolidation ends; a pivot can sit inside a final push. Measuring from
    // that true extreme keeps a valid flag whose pole extended slightly, while
    // the spec's 38% retrace rule still rejects deep reversal channels.
    const extremes = windowExtremes(candles, legEnd.index, consolidationEnd);
    const poleEndPrice = bullish
      ? Math.max(legEnd.price, extremes.high)
      : Math.min(legEnd.price, extremes.low);
    const poleHeight = Math.abs(poleEndPrice - legStart.price);
    // A flag's channel must stay narrow for its whole life; measuring only at
    // the leg end lets a widening/deep pullback pass as a flag.
    const flagWidth = Math.max(widthAtConsolidationStart, widthAtConsolidationEnd);
    if (flagWidth <= 0 || poleHeight <= 0) continue;

    const touches = touchCount(after, upper, 'high', atr * config.touchToleranceAtr)
      + touchCount(after, lower, 'low', atr * config.touchToleranceAtr);
    if (touches < config.minTouchesPerLine * 2) continue;

    const points = sortPoints([
      toPoint(legStart, candles), toPoint(legEnd, candles),
      toPoint(highs[0], candles), toPoint(highs[1], candles),
      toPoint(lows[0], candles), toPoint(lows[1], candles),
    ]);
    const target = bullish ? poleEndPrice + poleHeight : poleEndPrice - poleHeight;
    const stopLoss = legStart.price;
    const quality = clampQuality(
      QUALITY_BASE
      + QUALITY_WIDTH_WEIGHT
        * (1 - Math.min(1, flagWidth / (poleHeight * (config.flag.channelMaxWidthPct / 100))))
      + QUALITY_TOUCH_WEIGHT * Math.min(1, touches / QUALITY_TOUCH_FULL),
    );

    // Spec §5: the impulse leg must not retrace more than maxRetracePct before
    // the flag is accepted; otherwise a deep reversal channel is mislabelled.
    // The retrace is measured on actual candles, not the extrapolated boundary.
    const durationRatio = (consolidationEnd - legEnd.index) / Math.max(1, legBars);
    const retrace = bullish ? poleEndPrice - extremes.low : extremes.high - poleEndPrice;
    if (!usedPairs.has(fingerprint)
      && flagImpulse && flagWidth <= (config.flag.channelMaxWidthPct / 100) * poleHeight
      && retrace <= (config.flag.maxRetracePct / 100) * poleHeight
      && durationRatio <= config.flag.maxDurationRatio) {
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
          invalidationBuffer,
        }, candles, config);
        if (flag) {
          out.push(flag);
          remember(fingerprint, span);
        }
      }
    }

    // پنانت: همان لگ، ولی دو خط همگرا (سقف پایین‌آینده و کف بالارونده).
    // عرض در شروع و پایان خودِ فشرده‌سازی سنجیده می‌شود؛ فرمول بریف عرض را در
    // legEnd (پیش از شروع فشرده‌سازی) می‌گرفت که برای خطوط همگرا هرگز کوچک نمی‌شود.
    const converge = widthAtConsolidationStart > 0
      && widthAtConsolidationEnd <= (1 - config.pennant.convergenceMin) * widthAtConsolidationStart;
    // جفتِ مشترک: اگر پرچم همین جفت را منتشر کرده، پرچم می‌ماند و پنانت اضافه نمی‌شود.
    // همان دروازه‌های عمق/طولِ پرچم برای پنانت هم لازم‌اند؛ بدون آن یک اصلاح ۷۰٪
    // شبیه «پنانت» برچسب می‌خورد.
    if (!usedPairs.has(fingerprint)
      && pennantImpulse && converge && legBars <= config.pennant.maxBars
      && retrace <= (config.pennant.maxRetracePct / 100) * poleHeight
      && durationRatio <= config.pennant.maxDurationRatio) {
      const pennant = emitPattern({
        kind: 'PENNANT',
        direction: bullish ? 'bullish' : 'bearish',
        family: 'continuation',
        points, upper, lower, target, stopLoss,
        quality: quality - PENNANT_QUALITY_PENALTY,
        maxBars: config.pennant.maxBars,
        invalidationBuffer,
      }, candles, config);
      if (pennant) {
        out.push(pennant);
        remember(fingerprint, span);
      }
    }
  }

  out.push(...detectTriangleFamily(pivots, candles, atr, config, usedPairs, usedSpans));
  return dedupe(out);
}

/**
 * مثلث/مستطیل/گُوه: هر پنجرهٔ چهار پیوت متوالی یک نامزد است، نه فقط دو سقف و کفِ
 * آخر سری. بدون این پیمایش، این سه خانواده هیچ نمونهٔ تاریخی‌ای به آمار نمی‌دادند.
 * ترتیب از تازه به کهنه است و هر جفت مرزی فقط یک‌بار منتشر می‌شود.
 * پیرترین نامزدها به emitPattern سپرده می‌شوند؛ همان‌جا پنجرهٔ خانواده و
 * وضعیت (تأییدشده/باطل/منقضی) تعیین می‌شود تا نمونه‌های تاریخیِ تأییدشده از دست نروند.
 */
function detectTriangleFamily(
  pivots: PivotPoint[],
  candles: readonly EngineCandle[],
  atr: number,
  config: PatternConfig,
  usedPairs: Set<string>,
  usedSpans: Array<[number, number]>,
): ChartPattern[] {
  const out: ChartPattern[] = [];
  const windows: Array<[PivotPoint, PivotPoint, PivotPoint, PivotPoint]> = [];
  for (let i = 0; i + 3 < pivots.length; i++) {
    windows.push([pivots[i]!, pivots[i + 1]!, pivots[i + 2]!, pivots[i + 3]!]);
  }
  windows.reverse();

  for (const window of windows) {
    const highPivots = window.filter((p) => p.kind === 'high');
    const lowPivots = window.filter((p) => p.kind === 'low');
    if (highPivots.length !== 2 || lowPivots.length !== 2) continue;
    const highs: [PivotPoint, PivotPoint] = [highPivots[0]!, highPivots[1]!];
    const lows: [PivotPoint, PivotPoint] = [lowPivots[0]!, lowPivots[1]!];
    // R-PAT-14: هر جفتی که هر الگویی (پرچم/پنانت/پنجرهٔ دیگر) مصرف کرده، دوباره ساخته نمی‌شود.
    const fingerprint = boundaryFingerprint(highs, lows);
    if (usedPairs.has(fingerprint)) continue;

    const startIndex = Math.min(highs[0]!.index, lows[0]!.index);
    const endIndex = Math.max(highs[1]!.index, lows[1]!.index);
    // همان فشرده‌سازیِ یک شکلِ منتشرشده دوباره توصیف نمی‌شود (guard هم‌پوشانیِ spec §5).
    if (usedSpans.some((range) => overlaps(range, [startIndex, endIndex]))) continue;
    const emitted = buildTriangleWindow(highs, lows, candles, atr, config, startIndex, endIndex);
    if (!emitted) continue;
    out.push(emitted);
    usedPairs.add(fingerprint);
    usedSpans.push([startIndex, endIndex]);
  }
  return out.reverse();
}

/** اولین شکلِ واجد شرایطِ یک پنجره؛ ترتیب اولویت همان ترتیب قبلی است. */
function buildTriangleWindow(
  highs: [PivotPoint, PivotPoint],
  lows: [PivotPoint, PivotPoint],
  candles: readonly EngineCandle[],
  atr: number,
  config: PatternConfig,
  startIndex: number,
  endIndex: number,
): ChartPattern | null {
  const { upper, lower } = lines(highs, lows, candles);
  const h1 = highs[0]!.price, h2 = highs[1]!.price;
  const l1 = lows[0]!.price, l2 = lows[1]!.price;
  const flat = config.triangle.flatToleranceAtr * atr;
  const span = Math.abs(highs[1]!.index - lows[1]!.index);
  if (span < config.triangle.minSpan) return null;
  // R-PAT-5: انقضا با پنجرهٔ هر خانواده در emitPattern اعمال می‌شود؛ گارد عرضی مثلث لازم نیست.

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
  // A triangle's first swing is a boundary swing, not the impulse leg before it.
  // When the first leg is the whole trend and only the last two pivots converge,
  // the window is a trend leg + pullback; measured in price, scale-free.
  const legPrice = (a: typeof points[number], b: typeof points[number]) => Math.abs(a.price - b.price);
  const firstLeg = legPrice(points[0]!, points[1]!);
  const laterLeg = Math.max(
    legPrice(points[1]!, points[2]!),
    legPrice(points[2]!, points[3]!),
    atr * 0.5,
  );
  const triangleLegsOk = firstLeg <= config.triangle.maxFirstLegRatio * laterLeg;
  const wedgeLegsOk = firstLeg <= config.wedge.maxFirstLegRatio * laterLeg;
  const height = Math.abs(h1 - l1);
  const upperEnd = lineValue(upper, endIndex);
  const lowerEnd = lineValue(lower, endIndex);
  // R-PAT-15: هدف/حد ضرر آینه‌ای بر اساس مرزها؛ خنثی (مستطیل/متقارن) پیش‌فرض صعودی را نگه می‌دارد.
  const targets = (direction: ChartPattern['direction']) => (direction === 'bearish'
    ? { target: lowerEnd - height, stopLoss: upperEnd + atr }
    : { target: upperEnd + height, stopLoss: lowerEnd - atr });
  const base = { points, upper, lower, family: 'continuation' as const, invalidationBuffer: config.invalidationBufferAtr * atr };

  const build = (kind: PatternKind, direction: ChartPattern['direction'], quality: number, maxBars: number) =>
    emitPattern({ ...base, ...targets(direction), kind, direction, quality, maxBars }, candles, config);

  if (triangleLegsOk && Math.abs(h2 - h1) <= flat && l2 > l1) return build('TRIANGLE_ASC', 'bullish', TRIANGLE_QUALITY, config.triangle.maxBars);
  if (triangleLegsOk && Math.abs(l2 - l1) <= flat && h2 < h1) return build('TRIANGLE_DESC', 'bearish', TRIANGLE_QUALITY, config.triangle.maxBars);
  if (triangleLegsOk && converging && h2 < h1 && l2 > l1) return build('TRIANGLE_SYM', 'neutral', SYMMETRIC_QUALITY, config.triangle.maxBars);
  const driftPct = (a: number, b: number) =>
    Math.abs(a - b) / Math.max(1, Math.min(Math.abs(a), Math.abs(b))) * 100;
  if (Math.abs(h2 - h1) <= config.rectangle.flatToleranceAtr * atr
    && Math.abs(l2 - l1) <= config.rectangle.flatToleranceAtr * atr
    && driftPct(h1, h2) <= config.rectangle.maxDriftPct
    && driftPct(l1, l2) <= config.rectangle.maxDriftPct) {
    // R-PAT-5: پنجرهٔ انقضای مستطیل، نه پنجرهٔ مثلث.
    return build('RECTANGLE', 'neutral', RECTANGLE_QUALITY, config.rectangle.maxBars);
  }
  if (wedgeLegsOk && wedgeConverging && h2 > h1 && l2 > l1) return build('WEDGE_RISING', 'bearish', WEDGE_QUALITY, config.wedge.maxBars);
  if (wedgeLegsOk && wedgeConverging && h2 < h1 && l2 < l1) return build('WEDGE_FALLING', 'bullish', WEDGE_QUALITY, config.wedge.maxBars);
  return null;
}

function dedupe(patterns: ChartPattern[]): ChartPattern[] {
  const seen = new Set<string>();
  return patterns.filter((p) => (seen.has(p.id) ? false : (seen.add(p.id), true)));
}
