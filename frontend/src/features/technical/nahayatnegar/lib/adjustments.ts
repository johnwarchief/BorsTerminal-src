import type { KLineData } from 'klinecharts';
import { parseCandleTimestamp } from '../../lib/jalaliDate';

/**
 * رویداد تعدیل. سرور (api/chart.py) برای هر رویداد فقط یک عدد می‌دهد:
 * نسبتِ گسستِ «قیمت پایه» در روزِ بازگشایی = اثرِ **ترکیبیِ** افزایش سرمایه و سود نقدی.
 * تفکیکِ سهمِ هر کدام از این یک عدد ممکن نیست (یک معادله، دو مجهول)، پس حالت‌های
 * جداگانهٔ «سود نقدی» / «افزایش سرمایه» / «عملکردی» دادهٔ پشتیبان ندارند.
 */
export interface CorporateAction {
  timestamp: number;
  dateStr: string;
  ratio: number;
}

/** حالت‌های تعدیلی که واقعاً با دادهٔ سرور قابل محاسبه‌اند */
export type AdjustmentMode = 'none' | 'combined';

export function getAdjustmentFactor(action: CorporateAction): number {
  return action.ratio > 0 ? Math.min(Math.max(action.ratio, 0.0001), 50) : 1.0;
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
    return rawCandles.map(c => ({ ...c }));
  }

  // مرتب‌سازی زمانی رویدادها از قدیم به جدید
  const sortedActions = [...actions].sort((a, b) => a.timestamp - b.timestamp);

  return rawCandles.map(candle => {
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
