// model/patterns/detectReversal.ts
import type { EngineCandle } from '../doubleTapEngine';
import type { PatternConfig } from './config';
import type { BoundaryLine, ChartPattern, PatternPoint } from './types';
import { findAlternatingPivots, type PivotPoint } from './pivots';
import { emitPattern, toPoint } from './geometry';

const quality = (headroom: number, tolerance: number) =>
  Math.round(55 + 35 * Math.max(0, Math.min(1, headroom / Math.max(tolerance, 1e-9))) + 10);

/**
 * نقاط باید صعودی باشند: emitPattern لنگر را آخرین نقطه می‌گیرد و اسکن شکست را
 * از بعد از لنگر شروع می‌کند؛ نقطهٔ نامرتب یعنی look-ahead.
 */
function ascendingPoints(pivots: readonly PivotPoint[], candles: readonly EngineCandle[]): PatternPoint[] {
  return pivots.map((p) => toPoint(p, candles)).sort((a, b) => a.index - b.index);
}

/** خروجی: الگوهای بازگشتی باز/تأییدشده؛ الگوهای منقضی در emitPattern حذف می‌شوند. */
export function detectReversal(
  candles: readonly EngineCandle[],
  atr: number,
  config: PatternConfig,
): ChartPattern[] {
  if (!Number.isFinite(atr) || atr <= 0) return [];
  const pivots = findAlternatingPivots(candles, config.pivLeft, config.pivRight);
  const out: ChartPattern[] = [];

  for (let i = 0; i + 4 < pivots.length; i++) {
    const [a, b, c, d, e] = pivots.slice(i, i + 5) as [PivotPoint, PivotPoint, PivotPoint, PivotPoint, PivotPoint];
    const heads = a.kind === 'high' && c.kind === 'high' && e.kind === 'high' && b.kind === 'low' && d.kind === 'low';
    const bottoms = a.kind === 'low' && c.kind === 'low' && e.kind === 'low' && b.kind === 'high' && d.kind === 'high';
    if (!heads && !bottoms) continue;
    const span = e.index - a.index;
    if (span < 6 || span > config.hs.maxBars || e.index < candles.length - config.hs.maxBars) continue;
    const points = ascendingPoints([a, b, c, d, e], candles);

    if (heads) {
      const middleHighest = c.price >= Math.max(a.price, e.price) + config.hs.headAboveShouldersAtr * atr;
      const shouldersAligned = Math.abs(a.price - e.price) <= config.hs.shouldersToleranceAtr * atr;
      if (middleHighest && shouldersAligned) {
        const neck: BoundaryLine = { from: toPoint(b, candles), to: toPoint(d, candles) };
        const top: BoundaryLine = { from: toPoint(c, candles), to: toPoint(c, candles) };
        const neckline = Math.min(b.price, d.price);
        const height = c.price - neckline;
        const emitted = emitPattern({
          kind: 'HEAD_SHOULDERS', direction: 'bearish', family: 'reversal',
          points,
          upper: top, lower: neck, neckline: neck,
          target: neckline - height, stopLoss: c.price + atr,
          quality: quality(height, config.hs.shouldersToleranceAtr * atr * 2),
          // R-PAT-5: پنجرهٔ انقضای خانوادهٔ سر و شانه.
          maxBars: config.hs.maxBars,
        }, candles, config);
        if (emitted) out.push(emitted);
      }
    }

    if (bottoms) {
      const middleLowest = c.price <= Math.min(a.price, e.price) - config.hs.headAboveShouldersAtr * atr;
      const shouldersAligned = Math.abs(a.price - e.price) <= config.hs.shouldersToleranceAtr * atr;
      if (middleLowest && shouldersAligned) {
        const neck: BoundaryLine = { from: toPoint(b, candles), to: toPoint(d, candles) };
        const bottom: BoundaryLine = { from: toPoint(c, candles), to: toPoint(c, candles) };
        const neckline = Math.max(b.price, d.price);
        const height = neckline - c.price;
        const emitted = emitPattern({
          kind: 'INVERSE_HEAD_SHOULDERS', direction: 'bullish', family: 'reversal',
          points,
          upper: neck, lower: bottom, neckline: neck,
          target: neckline + height, stopLoss: c.price - atr,
          quality: quality(height, config.hs.shouldersToleranceAtr * atr * 2),
          // R-PAT-5: همان پنجرهٔ سر و شانه برای آینهٔ آن.
          maxBars: config.hs.maxBars,
        }, candles, config);
        if (emitted) out.push(emitted);
      }
    }

    // سه‌قلو: سه قله/درهٔ هم‌سطح با دو دره/قلهٔ میانی.
    const tol = config.triple.levelToleranceAtr * atr;
    if (heads && Math.abs(a.price - c.price) <= tol && Math.abs(c.price - e.price) <= tol) {
      const neck: BoundaryLine = { from: toPoint(b, candles), to: toPoint(d, candles) };
      const top: BoundaryLine = { from: toPoint(a, candles), to: toPoint(e, candles) };
      const height = Math.max(a.price, c.price, e.price) - Math.min(b.price, d.price);
      const emitted = emitPattern({
        kind: 'TRIPLE_TOP', direction: 'bearish', family: 'reversal',
        points,
        upper: top, lower: neck, neckline: neck,
        target: Math.min(b.price, d.price) - height, stopLoss: Math.max(a.price, c.price, e.price) + atr,
        quality: quality(height, tol * 2),
        // R-PAT-5: پنجرهٔ انقضای خانوادهٔ سه‌قلو.
        maxBars: config.triple.maxBars,
      }, candles, config);
      if (emitted) out.push(emitted);
    }
    if (bottoms && Math.abs(a.price - c.price) <= tol && Math.abs(c.price - e.price) <= tol) {
      const neck: BoundaryLine = { from: toPoint(b, candles), to: toPoint(d, candles) };
      const bottom: BoundaryLine = { from: toPoint(a, candles), to: toPoint(e, candles) };
      const height = Math.max(b.price, d.price) - Math.min(a.price, c.price, e.price);
      const emitted = emitPattern({
        kind: 'TRIPLE_BOTTOM', direction: 'bullish', family: 'reversal',
        points,
        upper: neck, lower: bottom, neckline: neck,
        target: Math.max(b.price, d.price) + height, stopLoss: Math.min(a.price, c.price, e.price) - atr,
        quality: quality(height, tol * 2),
        // R-PAT-5: همان پنجرهٔ سه‌قلو برای آینهٔ آن.
        maxBars: config.triple.maxBars,
      }, candles, config);
      if (emitted) out.push(emitted);
    }
  }
  return out;
}
