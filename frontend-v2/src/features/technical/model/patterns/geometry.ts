// model/patterns/geometry.ts
import type { EngineCandle } from '../doubleTapEngine';
import type { PatternConfig } from './config';
import type {
  BoundaryLine, ChartPattern, PatternDirection, PatternFamily, PatternKind, PatternPoint,
} from './types';
import type { PivotPoint } from './pivots';

export function toPoint(pivot: PivotPoint, candles: readonly EngineCandle[]): PatternPoint {
  return { index: pivot.index, price: pivot.price, timestamp: candles[pivot.index]?.timestamp ?? 0 };
}

export function lineValue(line: BoundaryLine, index: number): number {
  const span = Math.max(1, line.to.index - line.from.index);
  const slope = (line.to.price - line.from.price) / span;
  return line.from.price + slope * (index - line.from.index);
}

export function lineSlope(line: BoundaryLine): number {
  return (line.to.price - line.from.price) / Math.max(1, line.to.index - line.from.index);
}

export function touchCount(
  pivots: readonly PivotPoint[],
  line: BoundaryLine,
  kind: 'high' | 'low',
  tolerance: number,
): number {
  return pivots.filter(
    (p) => p.kind === kind && p.index >= line.from.index && p.index <= line.to.index
      && Math.abs(p.price - lineValue(line, p.index)) <= tolerance,
  ).length;
}

export function patternId(kind: PatternKind, anchorIndex: number, points: readonly PatternPoint[]): string {
  return `${kind}:${anchorIndex}:${points.map((p) => p.index).join('-')}`;
}

export interface PatternSpec {
  kind: PatternKind;
  direction: PatternDirection;
  family: PatternFamily;
  points: PatternPoint[];
  upper: BoundaryLine;
  lower: BoundaryLine;
  neckline?: BoundaryLine;
  target: number;
  stopLoss: number;
  quality: number;
  /** پنجرهٔ زمانی خانوادهٔ الگو؛ ریشهٔ الگو بیش از این مقدار عقب نماند. */
  maxBars: number;
  /**
   * بافرِ ابطال بر حسب قیمت (`invalidationBufferAtr × atr`)؛ دتکتور آن را می‌دهد
   * تا وضعیتِ منتشرشده با `outcomeOf` یک قاعدهٔ مشترک داشته باشد.
   */
  invalidationBuffer: number;
}

/**
 * وضعیت را از داده می‌سازد؛ الگوی منقضی (نه تأیید و نه باطل) حذف می‌شود.
 * ابطال با همان بافرِ outcome سنجیده می‌شود (invalidationBufferAtr) تا وضعیتِ
 * منتشرشده و نتیجهٔ آماری هرگز با هم اختلاف نداشته باشند: یک بستهٔ ۰٫۲×ATR
 * بیرونِ مرز هنوز «در حال تشکیل» است، نه «باطل».
 */
export function emitPattern(
  spec: PatternSpec,
  candles: readonly EngineCandle[],
  config: PatternConfig,
): ChartPattern | null {
  const anchor = spec.points[spec.points.length - 1];
  if (!anchor) return null;
  const maxBars = spec.maxBars;
  if (anchor.index < candles.length - maxBars - config.expiryGraceBars
    && spec.points.length < config.expiryMinPoints) return null;

  const start = anchor.index + 1;
  const buffer = spec.invalidationBuffer;
  let status: ChartPattern['status'] = 'forming';
  let breakoutIndex: number | undefined;

  for (let i = start; i < candles.length; i++) {
    const close = candles[i].close;
    const brokeUp = close > lineValue(spec.upper, i);
    const brokeDown = close < lineValue(spec.lower, i);
    // R-PAT-11: الگوی خنثی با شکست هر یک از دو مرز تأیید می‌شود و جهت خود را خنثی نگه می‌دارد.
    if (spec.direction === 'bullish' ? brokeUp
      : spec.direction === 'bearish' ? brokeDown : brokeUp || brokeDown) {
      status = 'confirmed';
      breakoutIndex = i;
      break;
    }
    if (spec.direction === 'bullish' ? close < lineValue(spec.lower, i) - buffer
      : spec.direction === 'bearish' ? close > lineValue(spec.upper, i) + buffer : false) {
      status = 'invalidated';
      break;
    }
  }
  if (status === 'forming' && anchor.index < candles.length - maxBars) return null;

  return {
    id: patternId(spec.kind, anchor.index, spec.points),
    kind: spec.kind,
    direction: spec.direction,
    family: spec.family,
    anchor,
    points: spec.points,
    upper: spec.upper,
    lower: spec.lower,
    neckline: spec.neckline,
    breakoutIndex,
    target: spec.target,
    stopLoss: spec.stopLoss,
    quality: Math.max(0, Math.min(100, Math.round(spec.quality))),
    status,
  };
}
