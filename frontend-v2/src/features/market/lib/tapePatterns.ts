export const STRONG_HOUR_LABEL = 'ساعت قوی — شانس صف فردا';
export const GOLDEN_HOUR_HINT =
  'ساعت طلایی: پایانی زیر دیروز بسته شده ولی آخرین معامله بالای دیروز است — خریدار پس از آفرِ پایانی قیمت را به مثبت برگردانده';
export const STRONG_CLOCK_HINT = '۹۰٪ احتمال بازگشایی مثبت فردا';
export const SWEEP_HINT =
  'کف‌روبی: صف فروش سنگین + جمع‌آوری درشت؛ سرانهٔ خرید ۳× در سطح ردیف نیست — نزدیک‌ترین معادلش قدرت خریدار است';

const CLOCK_DELTA_MIN_PCT = 1;

export type StrongHourInput = {
  p_last?: number | null;
  p_closing?: number | null;
  price_yesterday?: number | null;
};

export function lastCloseDiff(r: { p_last?: number | null; p_closing?: number | null }): number | null {
  const last = r.p_last;
  const close = r.p_closing;
  if (typeof last !== 'number' || typeof close !== 'number') return null;
  if (!Number.isFinite(last) || !Number.isFinite(close) || close === 0) return null;
  return (last - close) / close;
}

export function clockDeltaPct(r: { p_last?: number | null; p_closing?: number | null }): number | null {
  const diff = lastCloseDiff(r);
  return diff == null ? null : diff * 100;
}

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

export function detectGoldenHour(r: StrongHourInput): boolean {
  const close = r.p_closing;
  const last = r.p_last;
  const yesterday = r.price_yesterday;
  if (typeof close !== 'number' || typeof last !== 'number' || typeof yesterday !== 'number') return false;
  if (!Number.isFinite(close) || !Number.isFinite(last) || !Number.isFinite(yesterday)) return false;
  return close < yesterday && last > yesterday;
}
