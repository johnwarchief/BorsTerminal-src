/**
 * model/spotlight/adapter.ts
 *
 * آداپترهای خالص: `DoubleTapPattern` و `ChartPattern` → `SpotlightModel`.
 * هیچ محاسبهٔ چارت‌ای اینجا انجام نمی‌شود؛ فقط نگاشتِ فیلدها و سطوح.
 */
import type { DoubleTapPattern } from '../types';
import type { BoundaryLine, ChartPattern, PatternPoint } from '../patterns/types';
import { KIND_FA } from '../patterns/labels';
import type {
  SpotlightDirection,
  SpotlightModel,
  SpotlightScoreBreakdown,
  SpotlightStatus,
} from './types';

function lineValueAt(line: BoundaryLine, index: number): number {
  const span = line.to.index - line.from.index;
  if (span === 0) return line.to.price;
  const slope = (line.to.price - line.from.price) / span;
  return line.from.price + slope * (index - line.from.index);
}

/**
 * وضعیتِ الگوهای کلاسیک فقط سه حالت دارد؛ بقیهٔ حالت‌ها مخصوص چرخهٔ p12 است.
 * برای اطمینان، هر مقدار ناشناخته «تشکیل» تلقی می‌شود، نه تأیید.
 */
function classicStatus(status: ChartPattern['status']): SpotlightStatus {
  if (status === 'confirmed') return 'confirmed';
  if (status === 'invalidated') return 'invalidated';
  return 'forming';
}

function breakoutPoint(
  pattern: DoubleTapPattern,
): PatternPoint | undefined {
  if (pattern.breakoutIndex == null) return undefined;
  const price = pattern.breakoutPrice ?? pattern.neckline.price;
  return {
    index: pattern.breakoutIndex,
    price,
    timestamp: pattern.breakoutTs ?? pattern.retest?.timestamp ?? pattern.peak2.timestamp,
  };
}

export function doubleTapToSpotlight(p: DoubleTapPattern): SpotlightModel {
  const bullish = p.type === 'DOUBLE_BOTTOM';
  const side = p.breakoutIndex ?? p.retest?.index ?? p.peak2.index;
  const legs: PatternPoint[] = [
    ...(p.origin ? [p.origin] : []),
    p.peak1,
    p.neckline,
    p.peak2,
  ];
  const brk = breakoutPoint(p);
  if (brk) legs.push(brk);

  const scoreBreakdown: SpotlightScoreBreakdown | undefined = p.scoreBreakdown;

  return {
    id: p.id,
    source: 'doubleTap',
    kind: p.type,
    // برچسب اصلی p12 انگلیسی است؛ UIِ فارسی در جای دیگر می‌آید.
    kindLabel: bullish ? 'DOUBLE BOTTOM' : 'DOUBLE TOP',
    direction: bullish ? 'bullish' : 'bearish',
    status: p.status,
    grade: p.grade,
    score: p.p12Score ?? p.score,
    quality: p.quality,
    anchorIndex: side,
    points: [p.peak1, p.neckline, p.peak2],
    upper: Math.max(p.peak1.price, p.peak2.price),
    lower: Math.min(p.peak1.price, p.peak2.price),
    neckline: p.neckline.price,
    target: p.target1,
    stop: p.stopLoss,
    breakoutIndex: p.breakoutIndex,
    tp1: p.target1,
    tp2: p.target2,
    legs,
    scoreBreakdown,
    atr: p.atr,
  };
}

export function classicToSpotlight(p: ChartPattern): SpotlightModel {
  const direction: SpotlightDirection = p.direction;
  const anchor = p.anchor;
  const neckline = p.neckline ? lineValueAt(p.neckline, anchor.index) : undefined;
  return {
    id: `classic:${p.id}`,
    source: 'classic',
    kind: p.kind,
    kindLabel: KIND_FA[p.kind] ?? p.kind,
    direction,
    status: classicStatus(p.status),
    quality: p.quality,
    anchorIndex: anchor.index,
    points: [...p.points],
    upper: lineValueAt(p.upper, anchor.index),
    lower: lineValueAt(p.lower, anchor.index),
    neckline,
    target: p.target,
    stop: p.stopLoss,
    breakoutIndex: p.breakoutIndex,
    // برای الگوهای بدون neckline، هدف/حد ضرر همان الگو ریل TP/SL می‌سازند.
    tp1: p.target,
    legs: [...p.points],
    notes: neckline == null ? 'مرز شکست/تریگر' : undefined,
  };
}
