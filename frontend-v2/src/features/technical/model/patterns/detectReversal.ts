// model/patterns/detectReversal.ts
import type { EngineCandle } from '../doubleTapEngine';
import type { PatternConfig } from './config';
import type { BoundaryLine, ChartPattern, PatternPoint } from './types';
import { findAlternatingPivots, type PivotPoint } from './pivots';
import { emitPattern, lineValue, toPoint } from './geometry';

/**
 * وزن‌های امتیاز کیفیت؛ امتیازدهی‌اند نه دروازهٔ تحلیلی، پس در PATTERN_CONFIG نمی‌نشینند.
 * پایه + سقفِ سهم headroom = ۹۰؛ ثابت اشباعِ قبلی (+۱۰) امتیاز ۱۰۰ را در ۱٫۲ ATR
 * در دسترس می‌گذاشت، پس حذف شد و کف/سقف صریح‌اند.
 */
const QUALITY_BASE = 55;
const QUALITY_HEADROOM = 35;
const QUALITY_FLOOR = 10;
const QUALITY_CEILING = 100;

const quality = (headroom: number, tolerance: number) => {
  const ratio = Math.max(0, Math.min(1, headroom / Math.max(tolerance, 1e-9)));
  return Math.round(
    Math.max(QUALITY_FLOOR, Math.min(QUALITY_CEILING, QUALITY_BASE + QUALITY_HEADROOM * ratio)),
  );
};

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
    // R-PAT-16: کفِ span از config می‌آید؛ سقفِ پیش‌فیلتر بزرگ‌ترین پنجرهٔ دو خانواده است.
    const spanCap = Math.max(config.hs.maxBars, config.triple.maxBars);
    if (span < config.reversal.minSpanBars || span > spanCap || e.index < candles.length - spanCap) continue;
    const points = ascendingPoints([a, b, c, d, e], candles);

    if (heads) {
      const middleHighest = c.price >= Math.max(a.price, e.price) + config.hs.headAboveShouldersAtr * atr;
      const shouldersAligned = Math.abs(a.price - e.price) <= config.hs.shouldersToleranceAtr * atr;
      if (middleHighest && shouldersAligned) {
        const neck: BoundaryLine = { from: toPoint(b, candles), to: toPoint(d, candles) };
        const top: BoundaryLine = { from: toPoint(c, candles), to: toPoint(c, candles) };
        // ارتفاع اندازه‌گیری‌شده از مقدار خط گردن در لنگر، همان مرجعی که تأیید می‌سنجد.
        const neckAtAnchor = lineValue(neck, e.index);
        const height = c.price - neckAtAnchor;
        const emitted = emitPattern({
          kind: 'HEAD_SHOULDERS', direction: 'bearish', family: 'reversal',
          points,
          upper: top, lower: neck, neckline: neck,
          target: neckAtAnchor - height, stopLoss: c.price + atr,
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
        const neckAtAnchor = lineValue(neck, e.index);
        const height = neckAtAnchor - c.price;
        const emitted = emitPattern({
          kind: 'INVERSE_HEAD_SHOULDERS', direction: 'bullish', family: 'reversal',
          points,
          upper: neck, lower: bottom, neckline: neck,
          target: neckAtAnchor + height, stopLoss: c.price - atr,
          quality: quality(height, config.hs.shouldersToleranceAtr * atr * 2),
          // R-PAT-5: همان پنجرهٔ سر و شانه برای آینهٔ آن.
          maxBars: config.hs.maxBars,
        }, candles, config);
        if (emitted) out.push(emitted);
      }
    }

    // سه‌قلو: سه قله/درهٔ هم‌سطح با دو دره/قلهٔ میانی.
    const tol = config.triple.levelToleranceAtr * atr;
    // برابری سطح با دامنهٔ کل سنجیده می‌شود، نه زنجیرهٔ جفتی.
    const levelSpread = Math.max(a.price, c.price, e.price) - Math.min(a.price, c.price, e.price);
    if (heads && levelSpread <= tol) {
      const neck: BoundaryLine = { from: toPoint(b, candles), to: toPoint(d, candles) };
      const top: BoundaryLine = { from: toPoint(a, candles), to: toPoint(e, candles) };
      const neckAtAnchor = lineValue(neck, e.index);
      const height = Math.max(a.price, c.price, e.price) - neckAtAnchor;
      const emitted = emitPattern({
        kind: 'TRIPLE_TOP', direction: 'bearish', family: 'reversal',
        points,
        upper: top, lower: neck, neckline: neck,
        target: neckAtAnchor - height, stopLoss: Math.max(a.price, c.price, e.price) + atr,
        quality: quality(height, tol * 2),
        // R-PAT-5: پنجرهٔ انقضای خانوادهٔ سه‌قلو.
        maxBars: config.triple.maxBars,
      }, candles, config);
      if (emitted) out.push(emitted);
    }
    if (bottoms && levelSpread <= tol) {
      const neck: BoundaryLine = { from: toPoint(b, candles), to: toPoint(d, candles) };
      const bottom: BoundaryLine = { from: toPoint(a, candles), to: toPoint(e, candles) };
      const neckAtAnchor = lineValue(neck, e.index);
      const height = neckAtAnchor - Math.min(a.price, c.price, e.price);
      const emitted = emitPattern({
        kind: 'TRIPLE_BOTTOM', direction: 'bullish', family: 'reversal',
        points,
        upper: neck, lower: bottom, neckline: neck,
        target: neckAtAnchor + height, stopLoss: Math.min(a.price, c.price, e.price) - atr,
        quality: quality(height, tol * 2),
        // R-PAT-5: همان پنجرهٔ سه‌قلو برای آینهٔ آن.
        maxBars: config.triple.maxBars,
      }, candles, config);
      if (emitted) out.push(emitted);
    }
  }
  return out;
}
