import type { KLineData } from 'klinecharts';
import { parseCandleTimestamp } from '../../lib/jalaliDate';

/**
 * انواع رویدادهای مجمع و شرکتی بورس تهران
 */
export interface CorporateAction {
  timestamp: number;
  dateStr: string;
  type: 'dps' | 'capital_bonus' | 'capital_cash' | 'combined';
  dpsAmount?: number;
  bonusPercent?: number; // درصد سهام جایزه از انباشته/تجدید ارزیابی
  cashPercent?: number;  // درصد افزایش سرمایه از آورده نقدی و مطالبات
  preMeetingPrice: number;  // قیمت پایانی پیش از مجمع
  postMeetingPrice: number;
  /** نسبت گسست قیمت پایهٔ سرور (adjustEvents: {date,ratio}) — تنها منبع تعدیلِ واقعی */
  ratio?: number; // قیمت بازگشایی پس از مجمع
}

/**
 * ساختار خام رویدادهای مجمع از بک‌اند (adjustEvents) — همهٔ فیلدها اختیاری
 * چون بک‌اند ممکن است نام‌های مختلفی برای یک مفهوم ارسال کند.
 */
interface BackendAdjustEvent {
  timestamp?: number;
  time?: number;
  date?: string;
  dateStr?: string;
  /** بک‌اند موظف است یکی از مقادیر مجاز CorporateAction.type را ارسال کند */
  type?: CorporateAction['type'];
  dpsAmount?: number;
  dps?: number;
  bonusPercent?: number;
  bonus?: number;
  cashPercent?: number;
  cash?: number;
  preMeetingPrice?: number;
  pPre?: number;
  p_pre?: number;
  postMeetingPrice?: number;
  pPost?: number;
  p_post?: number;
  ratio?: number;
}

/**
 * حالت‌های ۶‌گانه تعدیل قیمت در بورس تهران
 */
export type AdjustmentMode =
  | 'none'          // بدون تعدیل (قیمت خام تابلو)
  | 'capital'       // افزایش سرمایه (فقط سهام جایزه و آورده)
  | 'cash'          // سود نقدی (فقط DPS)
  | 'capital_cash'  // افزایش سرمایه و سود نقدی (مجموع بازده تئوریک)
  | 'with_rights'   // با احتساب آورده (لحاظ ارزش اسمی ۱۰۰۰ ریالی حق تقدم)
  | 'operational';  // تعدیل عملکردی (بر مبنای قیمت کشف‌شده در بازگشایی واقعی)

/**
 * محاسبه ضریب تعدیل هر رویداد شرکتی
 */
export function getAdjustmentFactor(action: CorporateAction, mode: AdjustmentMode): number {
  if (mode === 'none') return 1.0;

  // منبع واحد حقیقت: سرور فقط «نسبت گسست قیمت پایه» را می‌دهد (adjustEvents=[{date,ratio}]).
  // هر تعدیلِ واقعی همان ratio است؛ در داده تفکیک سود/سهام/آورده نیست، پس همان ratio اعمال می‌شود
  // (نه فرمول ساختگی). این تنها مسیرِ داده‌پشتیبان است.
  if (typeof action.ratio === 'number' && action.ratio > 0) {
    return Math.max(0.0001, action.ratio);
  }

  const P_pre = action.preMeetingPrice;
  const P_post = action.postMeetingPrice;
  const dps = action.dpsAmount ?? 0;
  const a_bonus = (action.bonusPercent ?? 0) / 100;
  const a_cash = (action.cashPercent ?? 0) / 100;
  const total_alpha = a_bonus + a_cash;

  switch (mode) {
    case 'cash':
      // فقط اثر سود نقدی
      if (P_pre <= 0) return 1.0;
      return Math.max(0.001, (P_pre - dps) / P_pre);

    case 'capital':
      // فقط اثر افزایش سرمایه
      if (total_alpha <= 0) return 1.0;
      return 1 / (1 + total_alpha);

    case 'capital_cash': {
      // فرمول استاندارد مجموع بازده (بدون لحاظ آورده ۱۰۰۰ ریالی)
      if (P_pre <= 0) return 1.0;
      const p_theo = (P_pre - dps) / (1 + total_alpha);
      return Math.max(0.001, p_theo / P_pre);
    }

    case 'with_rights': {
      // فرمول با احتساب ارزش اسمی آورده (۱۰۰۰ ریال به ازای حق تقدم)
      if (P_pre <= 0) return 1.0;
      const p_theo = (P_pre - dps + a_cash * 1000) / (1 + total_alpha);
      return Math.max(0.001, p_theo / P_pre);
    }

    case 'operational': {
      // تعدیل عملکردی (روش نهایت‌نگر و ره‌آورد):
      // بر مبنای بازده واقعی پس از بازگشایی سهم در بازار
      // مخرج: P_post * (1 + alpha) + dps - (1000 * a_cash)
      const denom = P_post * (1 + total_alpha) + dps - (1000 * a_cash);
      if (denom <= 0) {
        return total_alpha > 0 ? 1 / (1 + total_alpha) : 1.0;
      }
      return Math.max(0.001, P_post / denom);
    }

    default:
      return 1.0;
  }
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
        cumulativeFactor *= getAdjustmentFactor(act, mode);
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
 * نگاشت رویدادهای خام بک‌اند adjustEvents به CorporateAction
 */
export function mapBackendAdjustEvents(rawEvents: BackendAdjustEvent[]): CorporateAction[] {
  if (!Array.isArray(rawEvents)) return [];

  return rawEvents
    .map(e => {
      const ts = parseCandleTimestamp(e.timestamp ?? e.time ?? e.dateStr ?? e.date);

      return {
        timestamp: Number.isFinite(ts) && ts > 0 ? ts : Date.now(),
        dateStr: e.dateStr || e.date || '',
        type: e.type || (e.bonusPercent ? 'capital_bonus' : e.dpsAmount ? 'dps' : 'combined'),
        dpsAmount: Number(e.dpsAmount ?? e.dps ?? 0),
        bonusPercent: Number(e.bonusPercent ?? e.bonus ?? 0),
        cashPercent: Number(e.cashPercent ?? e.cash ?? 0),
        preMeetingPrice: Number(e.preMeetingPrice ?? e.pPre ?? e.p_pre ?? 0),
        postMeetingPrice: Number(e.postMeetingPrice ?? e.pPost ?? e.p_post ?? 0),
        ratio: typeof e.ratio === 'number' && e.ratio > 0 ? e.ratio : undefined
      };
    })
    .filter(a => Number.isFinite(a.timestamp) && a.timestamp > 0);
}

