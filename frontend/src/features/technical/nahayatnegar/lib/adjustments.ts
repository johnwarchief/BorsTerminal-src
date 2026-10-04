import type { KLineData } from 'klinecharts';
import { parseCandleTimestamp } from '../../lib/jalaliDate';

/**
 * رویداد تعدیل. سرور (api/chart.py) برای هر رویداد فقط یک عدد می‌دهد:
 * نسبتِ گسستِ «قیمت پایه» در روزِ بازگشایی = اثرِ **ترکیبیِ** افزایش سرمایه و سود نقدی.
 * تفکیکِ سهمِ هر کدام از این یک عدد ممکن نیست (یک معادله، دو مجهول)، پس حالت‌های
 * جداگانهٔ «سود نقدی» و «افزایش سرمایه» دادهٔ پشتیبان ندارند.
 */
export interface CorporateAction {
  timestamp: number;
  dateStr: string;
  ratio: number;
}

/**
 * سه مفهومِ جدا — یکی نکن، جای یکی را به دیگری ندِه:
 *   none        — قیمتِ خامِ تابلو (محور ریال)
 *   combined    — ضریبِ تجمعیِ گسستِ «قیمت پایه» روی کندل‌هایِ ماقبلِ رویداد (محور ریال)
 *   performance — **نمایِ بازدهی (شاخصِ ۱۰۰)**: همان سریِ combined تقسیم بر نخستین
 *                 پایانی × ۱۰۰. مقدارِ `performance` درِ این فایل و درِ stateِ ذخیره‌شده
 *                 فقط نامِ سیمِ رابط است (نمایه‌هایِ چارت با همین رشته ذخیره شده‌اند)؛
 *                 معنایش شاخصِ بازدهی است، **نه** Functional Adjustment.
 *
 * «تعدیل عملکردیِ واقعی» (ره‌آورد/نهایات‌نگر) سودِ نقدی را **سرمایه‌گذاریِ دوباره**
 * می‌کند (history را تا ده برابر پایین‌تر می‌کشند — docs/CHART-PARITY-REFERENCE.md §۸)
 * و به DPSِ تفکیکیِ هر رویداد، آورده/حق‌تقدم، افزایشِ سرمایه و تاریخِ معافیت نیاز دارد.
 * هیچ‌یک از این‌ها درِ فیدِ TSETMC و درِ هیچ جدولِ این بانک نیست؛ پس این حالت اینجا
 * ساخته نمی‌شود و در `capability.functionalAvailable` صریح `false` می‌ماند.
 * هیچ عددِ حدسی به‌جایِ آن نمی‌نشیند.
 */
export type AdjustmentMode = 'none' | 'combined' | 'performance';

/** پایهٔ نمایِ بازدهی — همان چیزی که رویِ محورِ عمودی خوانده می‌شود */
export const PERFORMANCE_BASE = 100;

/** آنچه سرور دربارهٔ تواناییِ تعدیل اعلام می‌کند (api/chart.py::_adjust_capability) */
export interface AdjustmentCapability {
  /** منبعِ داوری: base-price-discontinuity · no-adjustment-event · local-cache ·
   *  base-not-anchored · local-db-unseen · … */
  source: string;
  /** مجموعهٔ رویدادِ کاننیکال در دسترس است ⇒ `combined` معنایِ واقعی دارد */
  combinedAvailable: boolean;
  /** تعدیلِ عملکردیِ واقعی (DPSِ سرمایه‌گذاری‌شده) — با دادهٔ این برنامه هیچ‌گاه true نیست */
  functionalAvailable: boolean;
  /** دلیلِ human-readableِ نبودِ تعدیلِ عملکردی (متنِ سرور، بی‌بازنویسی) */
  functionalReason: string;
  eventCount: number;
}

const UNKNOWN_CAPABILITY: AdjustmentCapability = {
  source: 'unreported',
  combinedAvailable: false,
  functionalAvailable: false,
  functionalReason: 'پاسخِ سرور بلوکِ تواناییِ تعدیل ندارد؛ تعدیلِ رویداد تأیید نشده است.',
  eventCount: 0,
};

/**
 * خواندنِ `adjustCapability` از پاسخِ سرور. نبودِ بلوک = «تأیید نشده»، نه «هست».
 * بی‌این، پاسخِ قدیمی/جایگزین با `adjustEvents: []` خودش را «رویدادی نیست» جا می‌زد.
 */
export function readAdjustmentCapability(raw: unknown): AdjustmentCapability {
  const c = (raw as { adjustCapability?: Record<string, unknown> } | null | undefined)?.adjustCapability;
  if (!c || typeof c !== 'object') {
    return { ...UNKNOWN_CAPABILITY, source: String((raw as { adjustSource?: unknown } | null)?.adjustSource ?? 'unreported') };
  }
  return {
    source: String(c.source ?? 'unreported'),
    combinedAvailable: c.combined_available === true,
    functionalAvailable: c.functional_available === true,
    functionalReason: String(c.functional_reason ?? UNKNOWN_CAPABILITY.functionalReason),
    eventCount: Number(c.event_count ?? 0) || 0,
  };
}

/**
 * هشدارِ صادقِ همان حالت — نه «داده نیست» کلی، بلکه علتِ همان محور.
 * فقط وقتی آتش می‌زند که مجموعهٔ رویداد در دسترس نباشد؛ آن‌وقت هر عددی که
 * `combined` یا «نمایِ بازدهی» خوانده می‌شود در واقع ریالِ خام است.
 */
export function adjustmentGapNote(mode: AdjustmentMode, cap: AdjustmentCapability): string | null {
  if (mode === 'none') return null;
  if (cap.combinedAvailable) return null;
  return mode === 'performance'
    ? `نمایِ بازدهی رویِ قیمتِ خام (تعدیلِ رویداد در دسترس نیست — منبع: ${cap.source}).`
    : `تعدیلِ ترکیبی در دسترس نیست (منبع: ${cap.source})؛ اعدادِ محور خام‌اند.`;
}

/** ده‌دقیقه‌ایِ ممیز برای عددِ بازدهی؛ قیمتِ ریالی گردِ صحیح می‌ماند */
function round2(v: number): number {
  return Math.round(v * 100) / 100;
}

export function getAdjustmentFactor(action: CorporateAction): number {
  return action.ratio > 0 ? Math.min(Math.max(action.ratio, 0.0001), 50) : 1.0;
}

/**
 * تبدیلِ سریِ قیمت به شاخصِ بازدهی: هر کندل ÷ پایانیِ نخستین کندل × ۱۰۰.
 * این **فقط یک مقیاس‌کردن است** — هیچ رویدادِ شرکتی در آن لحاظ نمی‌شود، پس
 * «تعدیل» نامیده نمی‌شود مگر رویِ سریِ از پیش `combined`.
 *
 * حجم و گردشِ ارزش **دست‌نخورده** می‌مانند — آن‌ها قیمت نیستند که مقیاس شوند.
 * سریِ بی‌پایه (نخستین close صفر یا تهی) بدونِ تغییر برمی‌گردد: تقسیمِ بر صفر
 * یعنی بی‌نهایتِ سبزِ جعلی رویِ محور، نه «۰٪».
 */
export function toIndexedSeries(candles: KLineData[]): KLineData[] {
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

/** دقتِ محورِ قیمت برای هر حالت — نمایِ بازدهی بدونِ دو رقمِ ممیز خوانده نمی‌شود */
export function pricePrecisionFor(mode: AdjustmentMode): number {
  return mode === 'performance' ? 2 : 0;
}

/**
 * تنها نسخهٔ ضربِ ضریبِ تعدیل در کل مرورگر. هیچ مصرف‌کننده‌ای (چارت، تجمیعِ
 * هفتگی/ماهانه، FFC، موتورِ دوم) نباید دوباره این را بنویسد یا خروجیِ این را
 * یک‌بارِ دیگر ضرب کند — «تعدیلِ دوباره» تاریخِ گذشته را دو‌بار مقیاس می‌کند.
 *
 * اعمال ضرایب تعدیل بر روی سری زمانی کندل‌ها (KLineData v10)
 */
export function applyAdjustmentToCandles(
  rawCandles: KLineData[],
  actions: CorporateAction[],
  mode: AdjustmentMode
): KLineData[] {
  if (mode === 'none' || !actions || actions.length === 0 || !rawCandles || rawCandles.length === 0) {
    return mode === 'performance' ? toIndexedSeries(rawCandles.map(c => ({ ...c })))
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

  // نمایِ بازدهی رویِ همان سریِ تعدیل‌شده می‌نشیند؛ بی‌ضریبِ قیمتی، درصدِ بازدهی
  return mode === 'performance' ? toIndexedSeries(scaled) : scaled;
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
