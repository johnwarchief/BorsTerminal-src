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

/** کاپ/کاپ معکوس: دو لبهٔ هم‌تراز، کفِ گرد، دستهٔ الزامیِ کم‌عمق، شکستِ لبه. */
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
      // R-PA-7: دسته الزامی است — پیوتِ خلافِ جهت پس از لبهٔ دوم و داخلِ پنجرهٔ
      // cup.maxBars، با عمقِ اکیداً مثبت و حداکثر handleDepthPct درصدِ عمقِ کاپ.
      const handleWindowEnd = b.index + config.cup.maxBars;
      const handle = pivots.find(
        (p) => p.index > b.index && p.index <= handleWindowEnd && p.kind === midKind,
      );
      if (!handle) continue;
      const handleDepth = inverted ? handle.price - rim : rim - handle.price;
      if (!(handleDepth > 0) || handleDepth > (config.cup.handleDepthPct / 100) * depth) continue;
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
 * R-PA-8: همهٔ نقاط روی کندلِ واقعیِ اکسترممِ هر بخش ساخته می‌شوند و لنگر
 * (آخرین نقطه، قراردادِ `emitPattern` برای شروع اسکن شکست) خودِ کندلِ
 * اکسترممِ بخش میانی است؛ پس شکست پس از کف/سقف واقعی اسکن می‌شود، نه پس از
 * انتهای پنجره. هدف هم به‌اندازهٔ عمق از خطِ لبه فراتر می‌رود.
 */
function rounding(candles: readonly EngineCandle[], atr: number, config: PatternConfig): ChartPattern[] {
  const out: ChartPattern[] = [];
  const n = candles.length;
  if (n < config.rounding.minBars) return out;
  const from = Math.max(0, n - config.rounding.maxBars);
  const window = candles.slice(from);
  const third = Math.floor(window.length / 3);
  if (third < 1) return out;
  const first = window.slice(0, third);
  const middle = window.slice(third, third * 2);
  const last = window.slice(third * 2);
  const midStart = from + third;
  const lastStart = midStart + third;

  /** کندلِ اکسترممِ یک بخش: آفستِ نسبی و قیمتِ واقعیِ سقف (high) یا کف (low). */
  const extremeAt = (bars: readonly EngineCandle[], high: boolean): { offset: number; price: number } => {
    let offset = 0;
    for (let j = 1; j < bars.length; j++) {
      const better = high ? bars[j].high > bars[offset].high : bars[j].low < bars[offset].low;
      if (better) offset = j;
    }
    return { offset, price: high ? bars[offset].high : bars[offset].low };
  };

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

  // R-PA-6/R-PA-8: همهٔ دروازه‌ها از پیکربندی می‌آیند، نه عدد جادویی.
  const minDepth = config.rounding.minDepthAtr * atr;
  const minBulge = config.rounding.minBulgeAtr * atr;
  const endSkew = config.rounding.endSkewPct / 100;
  const firstLow = extremeAt(first, false);
  const lastLow = extremeAt(last, false);
  const midLow = extremeAt(middle, false);
  const bottomRim = (firstLow.price + lastLow.price) / 2;
  const bottomDepth = bottomRim - midLow.price;
  const bottoms = bottomDepth >= minDepth
    && midLow.price < Math.min(firstLow.price, lastLow.price - minBulge)
    && Math.abs(firstLow.price - lastLow.price) <= endSkew * bottomDepth
    && shareBeyondRim(bottomRim, false) >= config.rounding.curvatureMin;
  const firstHigh = extremeAt(first, true);
  const lastHigh = extremeAt(last, true);
  const midHigh = extremeAt(middle, true);
  const topRim = (firstHigh.price + lastHigh.price) / 2;
  const topDepth = midHigh.price - topRim;
  const tops = topDepth >= minDepth
    && midHigh.price > Math.max(firstHigh.price, lastHigh.price + minBulge)
    && Math.abs(firstHigh.price - lastHigh.price) <= endSkew * topDepth
    && shareBeyondRim(topRim, true) >= config.rounding.curvatureMin;
  if (!bottoms && !tops) return out;
  const inverted = tops;
  const depth = inverted ? topDepth : bottomDepth;
  const rim = inverted ? topRim : bottomRim;
  const kind: 'high' | 'low' = inverted ? 'high' : 'low';
  const left = inverted ? firstHigh : firstLow;
  const right = inverted ? lastHigh : lastLow;
  const extreme = inverted ? midHigh : midLow;
  const leftP = toPoint({ index: from + left.offset, price: left.price, kind }, candles);
  const rightP = toPoint({ index: lastStart + right.offset, price: right.price, kind }, candles);
  const anchorP = toPoint({ index: midStart + extreme.offset, price: extreme.price, kind }, candles);
  const emitted = emitPattern({
    kind: inverted ? 'ROUNDING_TOP' : 'ROUNDING_BOTTOM',
    direction: inverted ? 'bearish' : 'bullish',
    family: 'reversal',
    // لنگر آخرین نقطه است و روی کندلِ اکسترمم می‌نشیند تا اسکنِ شکست از بعدِ آن شروع شود.
    points: [leftP, rightP, anchorP],
    upper: inverted ? flatP(anchorP) : lineP(leftP, rightP),
    lower: inverted ? lineP(leftP, rightP) : flatP(anchorP),
    target: inverted ? rim - depth : rim + depth,
    stopLoss: inverted ? extreme.price + atr : extreme.price - atr,
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
