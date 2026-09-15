/**
 * الگوریتم‌های تعدیل قیمت در بورس تهران (مطابق سیستم نهایت‌نگر و ره‌آورد ۳۶۵)
 * انواع تعدیل:
 * 1. none: بدون تعدیل (Raw unadjusted prices)
 * 2. capital: افزایش سرمایه (Capital increase only)
 * 3. cash: سود نقدی (DPS only)
 * 4. capital_cash: افزایش سرمایه و سود نقدی (Total Return standard)
 * 5. operational: تعدیل عملکردی (جامع‌ترین متد بازار سرمایه ایران با اثر بازگشایی واقعی)
 */

export interface CorporateAction {
  timestamp: number; // تاریخ مجمع یا بازگشایی به میلی‌ثانیه
  dateStr: string;   // تاریخ شمسی / میلادی
  type: 'dps' | 'capital_bonus' | 'capital_cash' | 'combined';
  dpsAmount?: number;         // سود نقدی تقسیمی به ریال
  bonusPercent?: number;      // درصد افزایش سرمایه از انباشته / تجدید ارزیابی (سهام جایزه)
  cashPercent?: number;       // درصد افزایش سرمایه از آورده نقدی و مطالبات (حق تقدم ۱۰۰۰ ریالی)
  preMeetingPrice: number;    // قیمت پایانی قبل از بسته شدن مجمع
  postMeetingPrice: number;   // قیمت مچینگ بازگشایی سهم بعد از مجمع
}

export interface Candle {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  turnover?: number;
}

/**
 * محاسبه ضریب تعدیل عملکردی (Operational Adjustment Factor)
 * فرمول رسمی نهایت‌نگر / ره‌آورد:
 * در این روش، اثر سود نقدی و افزایش سرمایه بر اساس قیمت واقعی بازگشایی (Post Meeting Price)
 * و لحاظ ارزش اسمی آورده (۱۰۰۰ ریال به ازای حق تقدم) در کل قیمت‌های ماقبل مجمع ضرب می‌شود.
 */
export function getAdjustmentFactor(action: CorporateAction, mode: 'none' | 'capital' | 'cash' | 'capital_cash' | 'operational'): number {
  if (mode === 'none') return 1.0;

  const P_pre = action.preMeetingPrice;
  const P_post = action.postMeetingPrice;
  const dps = action.dpsAmount || 0;
  const a_bonus = (action.bonusPercent || 0) / 100;
  const a_cash = (action.cashPercent || 0) / 100;
  const total_alpha = a_bonus + a_cash;

  switch (mode) {
    case 'cash':
      // نسبت تغییر قیمت ناشی از DPS
      if (P_pre <= 0) return 1.0;
      return Math.max(0.01, (P_pre - dps) / P_pre);

    case 'capital':
      // فقط نسبت افزایش سرمایه
      return 1 / (1 + total_alpha);

    case 'capital_cash': {
      // افزایش سرمایه و سود نقدی کلاسیک تئوریک
      if (P_pre <= 0) return 1.0;
      const p_theo = (P_pre - dps + a_cash * 1000) / (1 + total_alpha);
      return p_theo / P_pre;
    }

    case 'operational': {
      // تعدیل عملکردی جامع:
      // مبنای محاسبه: بازدهی واقعی دارایی سهامدار با لحاظ قیمت پس از مجمع
      // K_op = P_post / [ P_post * (1 + total_alpha) + dps - (1000 * a_cash) ]
      const denominator = P_post * (1 + total_alpha) + dps - (1000 * a_cash);
      if (denominator <= 0) return 1 / (1 + total_alpha);
      return Math.max(0.001, P_post / denominator);
    }

    default:
      return 1.0;
  }
}

/**
 * اعمال ضرایب تعدیل بر روی سری زمانی کندل‌ها
 * کندل‌های قبل از هر رویداد شرکتی در حاصل‌ضرب ضرایب مجمع‌های بعدی ضرب می‌شوند.
 */
export function applyAdjustmentToCandles(
  rawCandles: Candle[],
  actions: CorporateAction[],
  mode: 'none' | 'capital' | 'cash' | 'capital_cash' | 'operational'
): Candle[] {
  if (mode === 'none' || actions.length === 0) {
    return rawCandles.map(c => ({ ...c }));
  }

  // مرتب‌سازی رویدادها بر اساس زمان از قدیم به جدید
  const sortedActions = [...actions].sort((a, b) => a.timestamp - b.timestamp);

  // محاسبه ضرایب تجمعی رویدادها
  return rawCandles.map(candle => {
    let cumulativeFactor = 1.0;

    for (const act of sortedActions) {
      if (candle.timestamp < act.timestamp) {
        const factor = getAdjustmentFactor(act, mode);
        cumulativeFactor *= factor;
      }
    }

    return {
      timestamp: candle.timestamp,
      open: Math.round(candle.open * cumulativeFactor),
      high: Math.round(candle.high * cumulativeFactor),
      low: Math.round(candle.low * cumulativeFactor),
      close: Math.round(candle.close * cumulativeFactor),
      volume: Math.round(candle.volume / cumulativeFactor),
      turnover: candle.turnover
    };
  });
}
