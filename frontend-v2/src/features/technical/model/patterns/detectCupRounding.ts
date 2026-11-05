// model/patterns/detectCupRounding.ts
import type { EngineCandle } from '../doubleTapEngine';
import type { PatternConfig } from './config';
import type { BoundaryLine, ChartPattern, PatternPoint } from './types';
import { findAlternatingPivots, type PivotPoint } from './pivots';
import { emitPattern, lineValue, toPoint } from './geometry';

const clampQ = (q: number) => Math.max(0, Math.min(100, Math.round(q)));
const lineP = (a: PatternPoint, b: PatternPoint): BoundaryLine => ({ from: a, to: b });
const flatP = (p: PatternPoint): BoundaryLine => ({ from: p, to: p });
const pt = (p: PivotPoint, candles: readonly EngineCandle[]): PatternPoint => toPoint(p, candles);

/** کاپ/کاپ معکوس: دو لبهٔ هم‌تراز، کفِ گرد، دستهٔ کم‌عمق، شکستِ لبه. */
function cups(pivots: PivotPoint[], candles: readonly EngineCandle[], atr: number, config: PatternConfig): ChartPattern[] {
  const out: ChartPattern[] = [];
  for (let i = 0; i + 2 < pivots.length; i++) {
    for (const inverted of [false, true]) {
      const rimKind = inverted ? 'low' : 'high';
      const midKind = inverted ? 'high' : 'low';
      const a = pivots[i]!, m = pivots[i + 1]!, b = pivots[i + 2]!;
      if (a.kind !== rimKind || b.kind !== rimKind || m.kind !== midKind) continue;
      const bars = b.index - a.index;
      if (bars < config.cup.minBars || bars > config.cup.maxBars) continue;
      const rim = (a.price + b.price) / 2;
      const rimTol = config.cup.rimToleranceAtr * atr;
      if (Math.abs(a.price - b.price) > rimTol) continue;
      const depth = inverted ? m.price - rim : rim - m.price;
      // R-PA-6: کفِ عمق از پیکربندی، نه عدد جادویی.
      if (depth < config.cup.minDepthAtr * atr) continue;
      const after = pivots.filter((p) => p.index > b.index && p.kind === midKind);
      const handle = after[0];
      if (handle && (inverted ? handle.price - rim : rim - handle.price) > (config.cup.handleDepthPct / 100) * depth) continue;
      const emitted = emitPattern({
        kind: inverted ? 'INVERSE_CUP_HANDLE' : 'CUP_HANDLE',
        direction: inverted ? 'bearish' : 'bullish',
        family: 'continuation',
        points: [a, m, b].map((p) => toPoint(p, candles)),
        upper: inverted ? flatP(pt(m, candles)) : lineP(pt(a, candles), pt(b, candles)),
        lower: inverted ? lineP(pt(a, candles), pt(b, candles)) : flatP(pt(m, candles)),
        target: inverted ? rim - depth : rim + depth,
        stopLoss: inverted ? m.price + atr : m.price - atr,
        quality: clampQ(55 + 35 * Math.min(1, depth / (4 * atr)) + 10 * (1 - Math.abs(a.price - b.price) / Math.max(rimTol, 1e-9))),
        tier: 1,
        maxBars: config.cup.maxBars,
        invalidationBuffer: config.invalidationBufferAtr * atr,
      }, candles, config);
      if (emitted) out.push(emitted);
    }
  }
  return out;
}

/**
 * گردشدن: سه‌بخشِ سری؛ بخشِ میانی پایین‌ترین (یا بالاترین) و دو سرِ هم‌تراز.
 * R-PA-5: علاوه بر عمق و هم‌ترازیِ لبه‌ها، سهم بسته‌های بخش میانی در سمتِ
 * نامطلوبِ خطِ لبه باید از `curvatureMin` کمتر نباشد؛ کفِ V تیز که بیشترِ
 * بخش میانی را نزدیک لبه می‌گذراند رد می‌شود، کاسهٔ گرد قبول.
 */
function rounding(candles: readonly EngineCandle[], atr: number, config: PatternConfig): ChartPattern[] {
  const out: ChartPattern[] = [];
  const n = candles.length;
  if (n < config.rounding.minBars) return out;
  const from = Math.max(0, n - config.rounding.maxBars);
  const window = candles.slice(from);
  const third = Math.floor(window.length / 3);
  if (third < 1) return out;
  const lows = (arr: readonly EngineCandle[]) => Math.min(...arr.map((c) => c.low));
  const highs = (arr: readonly EngineCandle[]) => Math.max(...arr.map((c) => c.high));
  const first = window.slice(0, third);
  const middle = window.slice(third, third * 2);
  const last = window.slice(third * 2);
  const midStart = from + third;

  /** سهم بسته‌های بخش میانی که زیرِ (یا بالایِ) خطِ لبهٔ افقی بسته شده‌اند. */
  const shareBeyondRim = (rim: number, above: boolean): number => {
    const rimLine = lineP(
      pt({ index: from, price: rim, kind: 'low' }, candles),
      pt({ index: n - 1, price: rim, kind: 'low' }, candles),
    );
    const counted = middle.filter((c, j) => {
      const level = lineValue(rimLine, midStart + j);
      return above ? c.close > level : c.close < level;
    }).length;
    return counted / middle.length;
  };

  // R-PA-6: کفِ عمق از پیکربندی؛ برای سقف عمق روی سقف‌ها سنجیده می‌شود، نه کف‌ها.
  const minDepth = config.rounding.minDepthAtr * atr;
  const bottomRim = (lows(first) + lows(last)) / 2;
  const topRim = (highs(first) + highs(last)) / 2;
  const bottomDepth = bottomRim - lows(middle);
  const topDepth = highs(middle) - topRim;
  const bottoms = bottomDepth >= minDepth
    && lows(middle) < Math.min(lows(first), lows(last) - atr)
    && Math.abs(lows(first) - lows(last)) <= 0.5 * bottomDepth
    && shareBeyondRim(bottomRim, false) >= config.rounding.curvatureMin;
  const tops = topDepth >= minDepth
    && highs(middle) > Math.max(highs(first), highs(last) + atr)
    && Math.abs(highs(first) - highs(last)) <= 0.5 * topDepth
    && shareBeyondRim(topRim, true) >= config.rounding.curvatureMin;
  if (!bottoms && !tops) return out;
  const inverted = tops;
  const depth = inverted ? topDepth : bottomDepth;
  const kindOf = inverted ? 'high' : 'low';
  const anchorP = toPoint({ index: n - 1, price: inverted ? highs(last) : lows(last), kind: kindOf }, candles);
  const midP = toPoint({ index: midStart, price: inverted ? highs(middle) : lows(middle), kind: kindOf }, candles);
  const leftP = toPoint({ index: from + third - 1, price: inverted ? highs(first) : lows(first), kind: kindOf }, candles);
  const emitted = emitPattern({
    kind: inverted ? 'ROUNDING_TOP' : 'ROUNDING_BOTTOM',
    direction: inverted ? 'bearish' : 'bullish',
    family: 'reversal',
    points: [leftP, midP, anchorP],
    upper: inverted ? flatP(midP) : lineP(leftP, anchorP),
    lower: inverted ? lineP(leftP, anchorP) : flatP(midP),
    target: inverted ? midP.price - depth : midP.price + depth,
    stopLoss: inverted ? midP.price + atr : midP.price - atr,
    quality: clampQ(60 + 30 * Math.min(1, depth / (3 * atr))),
    tier: 1,
    maxBars: config.rounding.maxBars,
    invalidationBuffer: config.invalidationBufferAtr * atr,
  }, candles, config);
  if (emitted) out.push(emitted);
  return out;
}

export function detectCupRounding(
  candles: readonly EngineCandle[],
  atr: number,
  config: PatternConfig,
): ChartPattern[] {
  if (!Number.isFinite(atr) || atr <= 0) return [];
  const pivots = findAlternatingPivots(candles, config.pivLeft, config.pivRight);
  return [...cups(pivots, candles, atr, config), ...rounding(candles, atr, config)];
}
