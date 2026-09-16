// features/fundamental/lib/epsHistory.ts -- وضعیت سابقهٔ EPS (شاخص ۲)
// یک منبع حقیقتِ واحد برای جدول غربالگری، نردبان EPS و drill-down شاخص ۲ تا
// برچسب و منطق در همهجا یکی باشد (قبلاً جدول «مردود — سابقهٔ ناقص» و نردبان
// «مردود در شاخص ۲ — سابقهٔ ناقص» می‌نوشتند).
//
// قاعدهٔ جزوه: گیت شاخص ۲ سابقهٔ ۳ سالهٔ EPS می‌خواهد.
//   • ≥۲ سالِ واقعی ولی <۳ سال → «مردود — سابقهٔ ناقص (۲ از ۳ سال)»:
//     همان سالهای موجود نمایش داده میشود (داده حیف نمیشود) ولی ردِ گیت صریح است.
//   • <۲ سال → داده برای هیچ قضاوتی کافی نیست ⇒ «شکاف داده» (سطر حذف نمیشود).
import { toFaDigits } from '@shared/lib/fmt';

/** سابقهٔ لازم شاخص ۲ (جزوهٔ FTS) */
export const EPS_REQUIRED_YEARS = 3;
/** کفِ نمایش: با کمتر از این تعداد سال، داده برای قضاوت کافی نیست */
export const EPS_MIN_SHOWN_YEARS = 2;
/**
 * دلیلِ واقعیِ ردِ شاخص ۲ وقتی همهٔ سال‌های لازم موجودند (شکست گیت — نه شکاف داده).
 * کاربر: «علت رد باید دقیقاً همان شکست واقعی باشد»؛ مثال ویسا با سری
 * [742, 1140, -8] ⇒ «شکست روند سودآوری — سقوط سود به زیان در سال آخر (‎-۸ ریال)».
 * اگر دلیلی قابل استنتاج نبود null برمی‌گردد (هیچ متن ساختگی).
 */
export function epsFailReason(opts: {
  series?: readonly (number | null | undefined)[] | null;
  slots?: readonly string[] | null;
  strictlyRising?: boolean | null;
  allProfitable?: boolean | null;
}): string | null {
  const series = Array.isArray(opts.series) ? opts.series : [];
  const real = series.filter((v): v is number => typeof v === 'number' && Number.isFinite(v));
  if (real.length === 0) return null;
  const slots = Array.isArray(opts.slots) ? opts.slots : [];
  const lastIdx = series.length - 1 - [...series].reverse().findIndex((v) => typeof v === 'number' && Number.isFinite(v));
  const last = series[lastIdx] as number;
  const slot = slots[lastIdx] ?? '';
  const slotFa = slot ? `سال ${toFaDigits(slot)}` : 'سال آخر';
  if (last < 0) {
    return `شکست روند سودآوری — سقوط سود به زیان در ${slotFa} (${toFaDigits(last)} ریال)`;
  }
  const anyLoss = opts.allProfitable === false || real.some((v) => v <= 0);
  if (anyLoss) {
    return 'شکست روند سودآوری — یکی از سال‌های سابقه زیان‌ده (یا صفر) بوده است';
  }
  if (opts.strictlyRising === false) {
    const prev = real[real.length - 2];
    return `روند EPS صعودی نیست — سود ${slotFa} (${toFaDigits(last)}) از سال قبل (${toFaDigits(prev)}) کمتر است`;
  }
  return null;
}

/** برچسب‌های علت‌دار شاخص ۲ — جای برچسب عمومی «شکاف داده» */
export const EPS_GAP_LABEL_LT2 = 'سابقهٔ EPS کمتر از ۲ سال';
export const EPS_GAP_LABEL_NONE = 'سابقهٔ EPS سالانه ثبت نشده';
/** برچسب علت‌دار سابقهٔ EPS بر اساس تعداد سال‌های واقعیِ موجود */
export function epsGapLabel(realYears: number): string {
  return realYears >= 1 ? EPS_GAP_LABEL_LT2 : EPS_GAP_LABEL_NONE;
}
/** testid یکسان برای برچسب «سابقهٔ ناقص» در جدول، نردبان و drill-down */
export const EPS_PARTIAL_TESTID = 'eps-partial-rejected';

export type EpsHistoryState = 'complete' | 'partial' | 'insufficient';

export interface EpsHistory {
  /** تعداد سالهای واقعیِ موجود */
  realYears: number;
  requiredYears: number;
  state: EpsHistoryState;
  /** برچسب یکسان «مردود در شاخص ۲ — سابقهٔ ناقص (X از Y سال)» — فقط در حالت partial */
  label: string;
}

/** تعداد سالهای واقعیِ سری (سلولهای null = سال غایب، شمرده نمیشوند) */
export function epsRealYears(series: readonly (number | null | undefined)[] | null | undefined): number {
  if (!Array.isArray(series)) return 0;
  return series.filter((v) => typeof v === 'number' && Number.isFinite(v)).length;
}

/** سری را به متن خوانا «قدیم ← جدید» تبدیل میکند؛ null = همین «—» */
export function epsSeriesText(
  series: readonly (number | null | undefined)[] | null | undefined,
): string | null {
  if (!Array.isArray(series) || series.length === 0) return null;
  return series
    /* F-10: toFixed(0) مقدار اعشاری کدال را گِرد می‌کرد (۴۵۴.۶۷ → ۴۵۵) و با کارت نماد نمی‌خواند؛
       حالا عدد صحیح بی‌اعشار و اعشاری با حداکثر ۲ رقم (بدون صفرِ اضافی) نمایش داده می‌شود. */
    .map((v) =>
      typeof v === 'number' && Number.isFinite(v)
        ? toFaDigits(Number.isInteger(v) ? String(v) : v.toFixed(2).replace(/\.?0+$/, ''))
        : '—',
    )
    .join(' ← ');
}

/** برچسب یکسانِ «۲ از ۳ سال»: داده هست، ولی سابقهٔ کاملِ گیت نیست */
export function epsPartialRejectLabel(
  realYears: number,
  requiredYears: number = EPS_REQUIRED_YEARS,
): string {
  return `مردود در شاخص ۲ — سابقهٔ ناقص (${toFaDigits(realYears)} از ${toFaDigits(requiredYears)} سال)`;
}

/**
 * وضعیت سابقهٔ EPS از روی خودِ داده:
 * - سری سالانه (سلولهای null = سال غایب) مبنای اول است.
 * - اگر سری هیچ سالِ واقعی نداشت، «تعداد سالهای اعلامیِ بکاند» (yearsAvailable)
 *   بهعنوان جانشین استفاده میشود — کلمپشده به سابقهٔ لازم تا هیچوقت
 *   «۴ از ۳ سال» یا عدد بزرگتر از واقع نمایش داده نشود.
 * - تصمیم قبول/مردود جزئیِ خودِ گیت همیشه با فیلد pass بکاند میماند (اینجا
 *   فقط تعداد سال و برچسب ساخته میشود؛ هیچ عددی جعل نمیشود).
 */
export function epsHistory(
  series: readonly (number | null | undefined)[] | null | undefined,
  requiredYears: number = EPS_REQUIRED_YEARS,
  yearsAvailable?: number | null,
): EpsHistory {
  const required = Math.max(1, Math.trunc(requiredYears) || EPS_REQUIRED_YEARS);
  const fromSeries = epsRealYears(series);
  const fromCount =
    typeof yearsAvailable === 'number' && Number.isFinite(yearsAvailable)
      ? Math.min(Math.max(0, Math.trunc(yearsAvailable)), required)
      : 0;
  const realYears = Math.max(fromSeries, fromCount);
  const state: EpsHistoryState =
    realYears >= required ? 'complete' : realYears >= EPS_MIN_SHOWN_YEARS ? 'partial' : 'insufficient';
  return {
    realYears,
    requiredYears: required,
    state,
    label: state === 'partial' ? epsPartialRejectLabel(realYears, required) : '',
  };
}
