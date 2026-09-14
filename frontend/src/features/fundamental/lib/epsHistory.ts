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
/** کفِ نمایش: با کمتر از این تعداد سال، «شکاف داده» — نه قضاوت */
export const EPS_MIN_SHOWN_YEARS = 2;
/** برچسب رسمیِ شکاف داده در کل نمای بنیادی */
export const EPS_GAP_LABEL = 'شکاف داده';
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
    .map((v) => (typeof v === 'number' && Number.isFinite(v) ? toFaDigits(v.toFixed(0)) : '—'))
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
