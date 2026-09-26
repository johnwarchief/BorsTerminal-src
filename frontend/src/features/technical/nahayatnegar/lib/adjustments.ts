import type { KLineData } from 'klinecharts';
import { parseCandleTimestamp } from '../../lib/jalaliDate';

/**
 * رویداد تعدیل. سرور (api/chart.py) برای هر رویداد فقط یک عدد می‌دهد:
 * نسبتِ گسستِ «قیمت پایه» در روزِ بازگشایی = اثرِ **ترکیبیِ** افزایش سرمایه و سود نقدی.
 * تفکیکِ سهمِ هر کدام از این یک عدد ممکن نیست (یک معادله، دو مجهول)، پس حالت‌های
 * جداگانهٔ «سود نقدی» و «افزایش سرمایه» دادهٔ پشتیبان ندارند. «عملکردی» با همان
 * یک عدد ساختنی است ولی نه به شکلِ ره‌آورد — توضیحِ خودِ حالت پایین.
 */
export interface CorporateAction {
  timestamp: number;
  dateStr: string;
  ratio: number;
}

/**
 * حالت‌های تعدیلی که واقعاً با دادهٔ سرور قابل محاسبه‌اند:
 *   none        — قیمتِ خامِ تابلو
 *   combined    — ضریبِ گسستِ «قیمت پایه» روی کندل‌هایِ ماقبلِ رویداد (محور ریال)
 *   performance — همان سریِ تعدیل‌شده، ولی رویِ **مقیاسِ بازدهی**: نخستین کندل = ۱۰۰
 *
 * «عملکردی» اینجا با «درصد» یکی است، نه با فرمولِ اختصاصیِ ره‌آورد/نهایات‌نگر: آن‌ها
 * سودِ نقدی را **سرمایه‌گذاریِ دوباره** می‌کنند (history را تا ده برابر پایین‌تر
 * می‌کشند — docs/CHART-PARITY-REFERENCE.md §۸) و این به DPSِ تفکیکیِ هر رویداد
 * نیاز دارد که در بانکِ ما نیست. پس این حالت صادقانه «نمایِ بازدهی» است، نه
 * بازتولیدِ عددِ آن‌ها؛ تفکیکِ آورده/سودِ نقدی از یک نسبتِ واحد ساختنی نیست.
 */
export type AdjustmentMode = 'none' | 'combined' | 'performance';

/** پایهٔ نمایِ بازدهی — همان چیزی که رویِ محورِ عمودی خوانده می‌شود */
export const PERFORMANCE_BASE = 100;

/** ده‌دقیقه‌ایِ ممیز برای عددِ بازدهی؛ قیمتِ ریالی گردِ صحیح می‌ماند */
function round2(v: number): number {
  return Math.round(v * 100) / 100;
}

export function getAdjustmentFactor(action: CorporateAction): number {
  return action.ratio > 0 ? Math.min(Math.max(action.ratio, 0.0001), 50) : 1.0;
}

/**
 * تبدیلِ سریِ قیمت به شاخصِ بازدهی: هر کندل ÷ پایانیِ نخستین کندل × ۱۰۰.
 *
 * حجم و گردشِ ارزش **دست‌نخورده** می‌مانند — آن‌ها قیمت نیستند که مقیاس شوند.
 * سریِ بی‌پایه (نخستین close صفر یا تهی) بدونِ تغییر برمی‌گردد: تقسیمِ بر صفر
 * یعنی بی‌نهایتِ سبزِ جعلی رویِ محور، نه «۰٪».
 */
export function toPerformanceSeries(candles: KLineData[]): KLineData[] {
  const base = candles.length ? Number(candles[0].close) : 0;
  if (!(base > 0)) return candles.map(c => ({ ...c }));
  return candles.map(c => ({
    ...c,
    open: round2(Number(c.open) / base * PERFORMANCE_BASE),
    high: round2(Number(c.high) / base * PERFORMANCE_BASE),
    low: round2(Number(c.low) / base * PERFORMANCE_BASE),
    close: round2(Number(c.close) / base * PERFORMANCE_BASE),
  }));
}

/** دقتِ محورِ قیمت برای هر حالت — «عملکردی» بدونِ دو رقمِ ممیز خوانده نمی‌شود */
export function pricePrecisionFor(mode: AdjustmentMode): number {
  return mode === 'performance' ? 2 : 0;
}

/**
 * اعمال ضرایب تعدیل بر روی سری زمانی کندل‌ها (KLineData v10)
 */
export function applyAdjustmentToCandles(
  rawCandles: KLineData[],
  actions: CorporateAction[],
  mode: AdjustmentMode
): KLineData[] {
  if (mode === 'none' || !actions || actions.length === 0 || !rawCandles || rawCandles.length === 0) {
    return mode === 'performance' ? toPerformanceSeries(rawCandles.map(c => ({ ...c })))
                                  : rawCandles.map(c => ({ ...c }));
  }

  // مرتب‌سازی زمانی رویدادها از قدیم به جدید
  const sortedActions = [...actions].sort((a, b) => a.timestamp - b.timestamp);

  const scaled = rawCandles.map(candle => {
    let cumulativeFactor = 1.0;

    // کندل‌های ماقبل هر مجمع، در ضریب آن مجمع ضرب می‌شوند
    for (const act of sortedActions) {
      if (candle.timestamp < act.timestamp) {
        cumulativeFactor *= getAdjustmentFactor(act);
      }
    }

    // قیمت‌ها ضرب و حجم معاملات بر ضریب تقسیم می‌شود تا ارزش معامله ثابت بماند
    const factor = cumulativeFactor;
    return {
      timestamp: candle.timestamp,
      open: Math.round(candle.open * factor),
      high: Math.round(candle.high * factor),
      low: Math.round(candle.low * factor),
      close: Math.round(candle.close * factor),
      volume: candle.volume !== undefined ? Math.round(candle.volume / factor) : undefined,
      turnover: candle.turnover
    };
  });

  // «عملکردی» رویِ همان سریِ تعدیل‌شده می‌نشیند؛ بی‌ضریبِ قیمتی، درصدِ بازدهی
  return mode === 'performance' ? toPerformanceSeries(scaled) : scaled;
}

/**
 * نگاشت رویدادهای خام بک‌اند adjustEvents ([{date,ratio}]) به CorporateAction
 *
 * رویدادِ بی‌تاریخ حذف می‌شود، نه «الان»: اگر timestamp به امروز بیفتد، حلقهٔ
 * applyAdjustmentToCandles هر کندلِ موجود را زیرِ آن تاریخ می‌بیند و کلِ سری را
 * یک‌جا مقیاس می‌کند. نسبتِ بیرونِ بازهٔ باورپذیر هم حذف می‌شود.
 */
export function mapBackendAdjustEvents(
  rawEvents: Array<{ timestamp?: number | null; time?: number | null; date?: string | null;
                    dateStr?: string | null; ratio?: number | null }>
): CorporateAction[] {
  if (!Array.isArray(rawEvents)) return [];

  return rawEvents
    .map(e => ({
      timestamp: parseCandleTimestamp(e.timestamp ?? e.time ?? e.dateStr ?? e.date),
      dateStr: e.dateStr || e.date || '',
      ratio: Number(e.ratio ?? 0)
    }))
    .filter(a => Number.isFinite(a.timestamp) && a.timestamp > 0 &&
                 a.ratio > 0.02 && a.ratio < 50);
}
