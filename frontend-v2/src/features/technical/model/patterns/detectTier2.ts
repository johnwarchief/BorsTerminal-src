// model/patterns/detectTier2.ts
import type { EngineCandle } from '../doubleTapEngine';
import type { PatternConfig } from './config';
import type { BoundaryLine, ChartPattern, PatternPoint } from './types';
import { findAlternatingPivots, type PivotPoint } from './pivots';
import { emitPattern, lineValue, toPoint } from './geometry';

const clampQ = (q: number) => Math.max(0, Math.min(100, Math.round(q)));
const lineP = (a: PatternPoint, b: PatternPoint): BoundaryLine => ({ from: a, to: b });
const p = (x: PivotPoint, candles: readonly EngineCandle[]) => toPoint(x, candles);

/** دیاموند (همگرا) و پهن‌شونده (واگرا): پنج پیوتِ متناوب با دو خطِ مرزی. */
function diamondOrBroadening(
  pivots: PivotPoint[],
  candles: readonly EngineCandle[],
  atr: number,
  config: PatternConfig,
): ChartPattern[] {
  const out: ChartPattern[] = [];
  for (let i = 0; i + 4 < pivots.length; i++) {
    const w = pivots.slice(i, i + 5) as [PivotPoint, PivotPoint, PivotPoint, PivotPoint, PivotPoint];
    const top = w[0].kind === 'high' && w[2].kind === 'high' && w[4].kind === 'high';
    const bottom = w[0].kind === 'low' && w[2].kind === 'low' && w[4].kind === 'low';
    if (!top && !bottom) continue;
    if (w[4].index - w[0].index > config.hs.maxBars) continue;
    // R-PA-10: در شکلِ کف، سقف‌ها (w[1]، w[3]) خطِ بالا و کف‌ها (w[0]، w[2]، w[4])
    // خطِ پایین‌اند؛ وگرنه خطِ کف‌ها بالای خطِ سقف‌ها می‌افتد و شکستِ صعودیِ
    // ساختگی داخلِ شکل تأیید می‌شود.
    const upper = top
      ? lineP(p(w[0], candles), p(w[4], candles))
      : lineP(p(w[1], candles), p(w[3], candles));
    const lower = top
      ? lineP(p(w[1], candles), p(w[3], candles))
      : lineP(p(w[0], candles), p(w[4], candles));
    const width = (idx: number) => Math.abs(lineValue(upper, idx) - lineValue(lower, idx));
    const start = width(w[0].index);
    const mid = width(w[2].index);
    const end = width(w[4].index);
    // R-PA-11: عرضِ میانه از خودِ پیوتِ میانی تا مرزِ مقابل سنجیده می‌شود؛ عرضِ
    // بینِ دو خطِ مرزی خطی است و «میانهٔ پهن‌تر از شروع» با تفاضلِ خطوط ممکن نیست.
    const midSpan = top
      ? w[2].price - lineValue(lower, w[2].index)
      : lineValue(upper, w[2].index) - w[2].price;
    if (!(start > 0) || !(end > 0)) continue;
    const converging = mid > end && midSpan > start
      && end <= (1 - config.tier2.diamondConvergeMin) * start;
    const broadening = end >= (1 + config.tier2.broadeningMin) * start;
    if (!converging && !broadening) continue;
    const kind = converging
      ? (top ? 'DIAMOND_TOP' : 'DIAMOND_BOTTOM')
      : (top ? 'BROADENING_TOP' : 'BROADENING_BOTTOM');
    const height = Math.abs(w[2].price - w[1].price);
    const emitted = emitPattern({
      kind,
      direction: top ? 'bearish' : 'bullish',
      family: 'reversal',
      points: w.map((x) => p(x, candles)),
      upper,
      lower,
      target: top ? Math.min(w[1].price, w[3].price) - height : Math.max(w[1].price, w[3].price) + height,
      stopLoss: top ? w[2].price + atr : w[2].price - atr,
      quality: clampQ(50 + 30 * Math.min(1, height / (2 * atr)) + 20 * Math.min(1, Math.abs(end - start) / start)),
      tier: 2,
      maxBars: config.hs.maxBars,
      invalidationBuffer: config.invalidationBufferAtr * atr,
    }, candles, config);
    if (emitted) out.push(emitted);
  }
  return out;
}

/**
 * جزیره: گپِ ورود و گپِ خروج هر دو ≥ islandGapAtr·atr؛ گپِ خروج حداکثر
 * islandMaxBlockBars کندل پس از ورود. لنگر تک‌نقطه‌ای است و maxBars خانواده
 * از islandMaxBars می‌آید (R-PA-9: بدون عدد جادویی).
 */
function island(candles: readonly EngineCandle[], atr: number, config: PatternConfig): ChartPattern[] {
  const out: ChartPattern[] = [];
  const gap = config.tier2.islandGapAtr * atr;
  for (let i = 1; i < candles.length - 2; i++) {
    const prev = candles[i - 1]!;
    const cur = candles[i]!;
    const upGap = cur.low - prev.high >= gap;
    const downGap = prev.low - cur.high >= gap;
    if (!upGap && !downGap) continue;
    const lastExit = Math.min(candles.length - 1, i + config.tier2.islandMaxBlockBars);
    // R-PA-11: گپِ خروج از اکسترممِ جاریِ بلوک (بیشترین سقف / کمترین کف تا این
    // کندل) سنجیده می‌شود، نه فقط از کندلِ ورود؛ وگرنه نوسانِ داخلیِ جزیره یک
    // «گپِ خروج» ساختگی می‌سازد.
    let blockHigh = cur.high;
    let blockLow = cur.low;
    for (let j = i + 1; j <= lastExit; j++) {
      const closeGap = upGap ? candles[j]!.high < blockLow - gap : candles[j]!.low > blockHigh + gap;
      if (!closeGap) {
        blockHigh = Math.max(blockHigh, candles[j]!.high);
        blockLow = Math.min(blockLow, candles[j]!.low);
        continue;
      }
      const block = candles.slice(i, j + 1);
      const islandHigh = Math.max(...block.map((c) => c.high));
      const islandLow = Math.min(...block.map((c) => c.low));
      const anchor = toPoint({ index: j, price: candles[j]!.close, kind: upGap ? 'low' : 'high' }, candles);
      const emitted = emitPattern({
        kind: 'ISLAND_REVERSAL',
        direction: upGap ? 'bearish' : 'bullish',
        family: 'reversal',
        points: [anchor],
        upper: lineP(toPoint({ index: i, price: islandHigh, kind: 'high' }, candles), anchor),
        lower: lineP(toPoint({ index: i, price: islandLow, kind: 'low' }, candles), anchor),
        target: upGap ? islandLow - (islandHigh - islandLow) : islandHigh + (islandHigh - islandLow),
        stopLoss: upGap ? islandHigh + atr : islandLow - atr,
        quality: 60,
        tier: 2,
        maxBars: config.tier2.islandMaxBars,
        invalidationBuffer: config.invalidationBufferAtr * atr,
      }, candles, config);
      if (emitted) out.push(emitted);
      break;
    }
  }
  return out;
}

/**
 * سه قله روی سقف‌ها (R-PA-13, R-PA-15): سه سقفِ پیاپی با تقدّمِ سخت و حداقل
 * شیبِ کلِ `threePeaksSlopeAtr`·atr، به‌علاوهٔ حداقل دو کفِ میانی.
 * برابریِ سطح دروازهٔ این دو گونه نیست (فقط در TRIPLE_TOP/TRIPLE_BOTTOM
 * می‌ماند)؛ وگرنه «سه سقفِ نزولی» با سه‌قلوی هم‌سطح قابل تفکیک نبود و در
 * فیلترِ R-PAT-6 همیشه حذف می‌شد.
 *   THREE_RISING_PEAKS  = h3 > h2 > h1 و h3 − h1 ≥ شیب → بازگشتیِ نزولی در سقف؛
 *   THREE_FALLING_PEAKS = h3 < h2 < h1 و h1 − h3 ≥ شیب → ادامه‌دهندهٔ نزولی.
 * کف‌ها گونه‌ای نمی‌سازند.
 */
function threePeaks(
  pivots: PivotPoint[],
  candles: readonly EngineCandle[],
  atr: number,
  config: PatternConfig,
): ChartPattern[] {
  const out: ChartPattern[] = [];
  const slopeFloor = config.tier2.threePeaksSlopeAtr * atr;
  const peaks = pivots.filter((x) => x.kind === 'high');
  for (let i = 0; i + 2 < peaks.length; i++) {
    const trio = peaks.slice(i, i + 3) as [PivotPoint, PivotPoint, PivotPoint];
    const [h1, h2, h3] = trio;
    // R-PA-11: همان سقفِ پنجرهٔ خانواده و پیش‌فیلترِ تازگیِ detectReversal؛
    // سه‌گانهٔ کش‌آمده یا کهنه نباید منتشر شود.
    if (h3.index - h1.index > config.hs.maxBars) continue;
    if (h3.index < candles.length - config.hs.maxBars) continue;
    const rising = h3.price > h2.price && h2.price > h1.price && h3.price - h1.price >= slopeFloor;
    const falling = h3.price < h2.price && h2.price < h1.price && h1.price - h3.price >= slopeFloor;
    if (!rising && !falling) continue;
    const level = Math.max(...trio.map((x) => x.price));
    const tween = pivots.filter((x) => x.index > h1.index && x.index < h3.index && x.kind === 'low');
    if (tween.length < 2) continue;
    const neck = lineP(p(tween[0]!, candles), p(tween[tween.length - 1]!, candles));
    const height = Math.abs(level - tween[0]!.price);
    const emitted = emitPattern({
      kind: falling ? 'THREE_FALLING_PEAKS' : 'THREE_RISING_PEAKS',
      direction: 'bearish',
      family: falling ? 'continuation' : 'reversal',
      points: trio.map((x) => p(x, candles)),
      upper: lineP(p(h1, candles), p(h3, candles)),
      lower: neck,
      target: neck.to.price - height,
      stopLoss: level + atr,
      quality: clampQ(55 + 30 * Math.min(1, height / (2 * atr)) + (falling ? 0 : 10)),
      tier: 2,
      maxBars: config.hs.maxBars,
      invalidationBuffer: config.invalidationBufferAtr * atr,
    }, candles, config);
    if (emitted) out.push(emitted);
  }
  return out;
}

export function detectTier2(
  candles: readonly EngineCandle[],
  atr: number,
  config: PatternConfig,
): ChartPattern[] {
  if (!Number.isFinite(atr) || atr <= 0) return [];
  const pivots = findAlternatingPivots(candles, config.pivLeft, config.pivRight);
  return [
    ...diamondOrBroadening(pivots, candles, atr, config),
    ...island(candles, atr, config),
    ...threePeaks(pivots, candles, atr, config),
  ];
}
