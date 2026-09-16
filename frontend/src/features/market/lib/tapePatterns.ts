// features/market/lib/tapePatterns.ts -- الگوهای تابلوخوانی روی ستِ ردیف تابلو
// فایل جدیدِ بالای tapeMath.ts (که آینهٔ بک‌اند است و دست‌نخورده می‌ماند).
// ساعت قوی: پایانی زیر دیروز بسته ولی آخرین بالای دیروز -- یعنی خریدار
// پس از آفرِ پایانی قیمت را به مثبت برگردانده و شانس صف خرید فردا بالاست.

export const STRONG_HOUR_LABEL = 'ساعت قوی — شانس صف فردا';
/** برچسب «ساعت طلایی»: پایانی منفی و آخرین مثبت (بازگشت خریدار بدون شرط دلتا) */
export const GOLDEN_HOUR_LABEL = 'ساعت طلایی — پایانی منفی و آخرین مثبت';
export const GOLDEN_HOUR_HINT =
  'ساعت طلایی: پایانی زیر دیروز بسته شده ولی آخرین معامله بالای دیروز است — خریدار پس از آفرِ پایانی قیمت را به مثبت برگردانده';
/** حداقل دلتای آخرین/پایانی برای «الگوی ساعت پیشرفته» (درصد) */
export const CLOCK_DELTA_MIN_PCT = 1;
/** برچسب احتمالِ ساعت قویِ پیشرفته (سند تابلوخوانی -- بازگشایی مثبت فردا) */
export const STRONG_CLOCK_HINT = '۹۰٪ احتمال بازگشایی مثبت فردا';

export type StrongHourInput = {
  p_last?: number | null;
  p_closing?: number | null;
  price_yesterday?: number | null;
};

/**
 * الگوی ساعت قوی (پیشرفته): پایانی زیر دیروز + آخرین بالای دیروز
 * و دلتای آخرین/پایانی حداقل ۱٪ -- یعنی خریدار پس از آفرِ پایانی
 * قیمت را نه‌فقط به مثبت، بلکه با فاصلهٔ معنادار برگردانده است.
 */
export function detectStrongHour(r: StrongHourInput): boolean {
  const close = r.p_closing;
  const last = r.p_last;
  const yesterday = r.price_yesterday;
  if (typeof close !== 'number' || typeof last !== 'number' || typeof yesterday !== 'number') return false;
  if (!Number.isFinite(close) || !Number.isFinite(last) || !Number.isFinite(yesterday)) return false;
  if (!(close < yesterday && last > yesterday)) return false;
  const delta = clockDeltaPct(r);
  return delta != null && delta >= CLOCK_DELTA_MIN_PCT;
}

export type StrongHourResult = { hit: boolean; label: string | null };

export function strongHour(r: StrongHourInput): StrongHourResult {
  return detectStrongHour(r) ? { hit: true, label: STRONG_HOUR_LABEL } : { hit: false, label: null };
}

/**
 * الگوی «ساعت طلایی»: پایانی زیر دیروز (منفی) و آخرین بالای دیروز (مثبت).
 * نسخهٔ سخت‌گیرانه‌تر (با دلتای ≥ ۱٪) همان detectStrongHour است؛ این تابع
 * لایهٔ پایه را جدا می‌کند تا بج «ساعت طلایی» از «ساعت معمولی» تفکیک شود.
 */
export function detectGoldenHour(r: StrongHourInput): boolean {
  const close = r.p_closing;
  const last = r.p_last;
  const yesterday = r.price_yesterday;
  if (typeof close !== 'number' || typeof last !== 'number' || typeof yesterday !== 'number') return false;
  if (!Number.isFinite(close) || !Number.isFinite(last) || !Number.isFinite(yesterday)) return false;
  return close < yesterday && last > yesterday;
}

/**
 * اختلاف آخرین و پایانی به نسبت پایانی: (p_last - p_closing) / p_closing
 * منفی یعنی پایانی بالاتر از آخرین (فشار آفر). مبنای ستون و سورتِ تابلو.
 */
export function lastCloseDiff(r: { p_last?: number | null; p_closing?: number | null }): number | null {
  const last = r.p_last;
  const close = r.p_closing;
  if (typeof last !== 'number' || typeof close !== 'number') return null;
  if (!Number.isFinite(last) || !Number.isFinite(close) || close === 0) return null;
  return (last - close) / close;
}

/** دلتای الگوی ساعت (درصد): ((p_last - p_closing) / p_closing) * 100 */
export function clockDeltaPct(r: { p_last?: number | null; p_closing?: number | null }): number | null {
  const diff = lastCloseDiff(r);
  return diff == null ? null : diff * 100;
}

/** ورودی ناهنجاری‌های تابلو -- همان ستون‌های /api/market */
export type TapeAnomalyInput = {
  f_roobi?: boolean | null;
  f_clock?: boolean | null;
  f_susp?: boolean | null;
  vol_ratio?: number | null;
  buyer_power?: number | null;
};

/** آستانهٔ «حجم بالا» برای کف‌روبی -- آینهٔ SUSP_VOL_MULT بدون دست‌زدن به tapeMath */
export const SWEEP_VOL_RATIO_MIN = 3;
/** نزدیک‌ترین معادلِ «سرانه خرید بالای ۳×» روی ستون‌های موجودِ تابلو */
export const SWEEP_BUYER_POWER_MIN = 1.5;
export const SWEEP_HINT =
  'کف‌روبی: صف فروش سنگین + جمع‌آوری درشت؛ سرانهٔ خرید ۳× در سطح ردیف نیست — نزدیک‌ترین معادلش قدرت خریدار است';

/** کف‌روبی: فیلتر بک‌اندِ روباهی + حجم بالا + قدرت خریدار (پروکسی سرانهٔ خرید) */
export function detectSweep(r: TapeAnomalyInput): boolean {
  if (!r.f_roobi) return false;
  const vr = r.vol_ratio;
  const bp = r.buyer_power;
  return typeof vr === 'number' && Number.isFinite(vr) && vr >= SWEEP_VOL_RATIO_MIN &&
    typeof bp === 'number' && Number.isFinite(bp) && bp >= SWEEP_BUYER_POWER_MIN;
}

export const BOX_EXIT_HINT = 'خروج از باکس رنج: ساعت + حجم مشکوک هم‌زمان — باکس دقیق ۳ هفته‌ای مالکیت چارت است';

/**
 * خروج از باکس رنج: ترکیب f_clock && f_susp. کانال افقی ۳ هفته‌ای در سطح
 * ردیف تابلو موجود نیست — این نزدیک‌ترین معادل روی همان فیلدهاست (mock نیست).
 */
export function detectBoxExit(r: TapeAnomalyInput): boolean {
  return !!r.f_clock && !!r.f_susp;
}
