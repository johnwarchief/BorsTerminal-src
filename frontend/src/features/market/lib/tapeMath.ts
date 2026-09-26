// features/market/lib/tapeMath.ts -- ریاضیات خالص تابلوخوانی
// آینهٔ منطقیِ tape_flags.py (بک‌اند) برایِ فیلترهایِ پنج‌گانهٔ تابلو. همه
// توابع خالص‌اند و null را امن برمی‌گردانند: **نبودنِ داده هیچ‌وقت «قبول»
// نیست** و هیچ دروازهِ‌ای با صفرِ جعلی باز نمی‌شود.
import type { MarketRow } from '@shared/types/marketRow';

/** شکاف الگوی ساعت: آخرین دست کم ۲ درصد بالاتر از پایانی (جزوه: pl >= pc*1.02) */
export const CLOCK_GAP = 0.02;
/** حد نصاب تعداد معاملات برای الگوی ساعت (بک اند: z_tot_tran > 30) */
export const CLOCK_MIN_TRADES = 30;
/** ضریب حجم مشکوک (بک اند: tvol > 3 * avg30 و tno > 50) */
export const SUSP_VOL_MULT = 3;
export const SUSP_MIN_TRADES = 50;
/** کف نسبت سرانه خرید حقیقی به فروش (جزوه f_jet: 1.5) */
export const PER_CAPITA_MIN = 1.5;
/** سقف نسبت قدرت خریدار (بک اند: clip بالای 10) */
export const BUYER_POWER_CAP = 10;
/** ضریب حجم فیلتر جت (جزوه: tvol > 3 * avg30) */
export const JET_VOL_MULT = 3;

/**
 * پلکانِ مقاومتِ فیلترِ جت، عینِ جزوه:
 *   [ih][2].PriceMax < pl && [ih][5] < pl && … && [ih][59].PriceMax < pl
 * [ih][1] درِ جزوه نیست؛ افزودنش شرطِ «سقفِ دیروز» را تحمیل می‌کند که
 * مالکِ برنامه آن را درِ فرمول نیاورده است.
 */
export const JET_LADDER = [2, 5, 9, 19, 29, 39, 49, 59] as const;

/** دسترسیٔ تایپ‌شده به [ih][k].PriceMax — به‌جای کلیدِ داینامیک روی MarketRow */
const LADDER_HIGH: Record<number, (r: MarketRow) => number | null | undefined> = {
  2: (r) => r.h2_max, 5: (r) => r.h5_max, 9: (r) => r.h9_max, 19: (r) => r.h19_max,
  29: (r) => r.h29_max, 39: (r) => r.h39_max, 49: (r) => r.h49_max, 59: (r) => r.h59_max,
};

function num(v: number | null | undefined): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

/**
 * اختلاف آخرین به پایانی به نسبت پایانی: (pLast - pClosing) / pClosing
 * همان تعریف قرارداد TapePayload.lastVsClose. مثبت یعنی آخرین معامله بالاتر از پایانی است.
 */
export function lastVsClose(pLast: number | null | undefined, pClosing: number | null | undefined): number | null {
  const last = num(pLast);
  const close = num(pClosing);
  if (last == null || close == null || close === 0) return null;
  return (last - close) / close;
}

/**
 * شکاف الگوی ساعت: (pLast - pClosing) / pClosing
 * طبق FTS_SPEC: اختلاف آخرین معامله از قیمت پایانی (plp - pcp >= 1.0). مثبت یعنی قدرت خریدار در پایان بازار.
 */
export function clockGap(pLast: number | null | undefined, pClosing: number | null | undefined): number | null {
  return lastVsClose(pLast, pClosing);
}
/** نام مستعار برای سازگاری عقب‌رو با تست‌ها */
export const closingGap = clockGap;

/** سرانه: حجم تقسیم بر تعداد. تعداد صفر یا نامعتبر یعنی null */
export function perCapita(vol: number | null | undefined, count: number | null | undefined): number | null {
  const v = num(vol);
  const c = num(count);
  if (v == null || c == null || c <= 0) return null;
  return v / c;
}

/**
 * نسبت قدرت خریدار حقیقی: سرانه خرید ÷ سرانه فروش، سقف 10.
 * هر طرف غیرقابل محاسبه باشد یعنی null (نسبت ساختنی نیست).
 */
export function buyerPowerRatio(
  buyVol: number | null | undefined,
  buyCount: number | null | undefined,
  sellVol: number | null | undefined,
  sellCount: number | null | undefined,
): number | null {
  const buy = perCapita(buyVol, buyCount);
  const sell = perCapita(sellVol, sellCount);
  if (buy == null || sell == null || sell === 0) return null;
  return Math.min(BUYER_POWER_CAP, buy / sell);
}

/** نسبت حجم امروز به میانگین ماهانه */
export function volumeMultiple(tvol: number | null | undefined, monthAvg: number | null | undefined): number | null {
  const t = num(tvol);
  const m = num(monthAvg);
  if (t == null || m == null || m <= 0) return null;
  return t / m;
}

export type ClockInput = {
  p_last?: number | null;
  p_closing?: number | null;
  tvol?: number | null;
  month_avg_vol?: number | null;
  z_tot_tran?: number | null;
};

export type ClockResult = { hit: boolean; gap: number | null };

/** الگوی ساعت FTS: آخرین معامله حداقل ۱٪ بالاتر از قیمت پایانی و حجم بالای میانگین */
export function detectClockPattern(r: ClockInput): ClockResult {
  const gap = clockGap(r.p_last, r.p_closing);
  const t = num(r.tvol);
  const m = num(r.month_avg_vol);
  const n = num(r.z_tot_tran);
  const hit =
    gap != null &&
    gap >= CLOCK_GAP &&
    t != null &&
    m != null &&
    m > 0 &&
    t > m &&
    n != null &&
    n > CLOCK_MIN_TRADES;
  return { hit, gap };
}

export type SuspInput = {
  tvol?: number | null;
  month_avg_vol?: number | null;
  z_tot_tran?: number | null;
};

export type SuspResult = { hit: boolean; multiple: number | null };

/** حجم مشکوک: حجم بیش از 3 برابر میانگین و معاملات بالای 50 */
export function detectSuspiciousVolume(r: SuspInput): SuspResult {
  const multiple = volumeMultiple(r.tvol, r.month_avg_vol);
  const n = num(r.z_tot_tran);
  const hit = multiple != null && multiple > SUSP_VOL_MULT && n != null && n > SUSP_MIN_TRADES;
  return { hit, multiple };
}

/**
 * سقفِ پلکانِ مقاومت تا تایم‌فریمِ خواسته‌شده.
 *
 * هر نقطه‌ای که از lookback کوتاه‌تر است باید شکسته شود، و هر نقطه‌ای که
 * وجود ندارد سنجش را ناممکن می‌کند → null. صفر بازگرداندن یعنی «سقفی نبود
 * که زیرش بمانیم» و فیلتر را برای نمادِ بی‌تاریخچه باز می‌گذارد — همان
 * حلقهٔ خاموشی که ۶۷۱ ردیف را جت می‌زد.
 */
export function resistanceLadderHigh(r: MarketRow, lookback: number): number | null {
  let hi: number | null = null;
  for (const k of JET_LADDER) {
    if (k > lookback) break;
    const v = num(LADDER_HIGH[k](r));
    if (v == null || v <= 0) return null;
    hi = hi === null ? v : Math.max(hi, v);
  }
  return hi;
}

/** نتیجهٔ فیلتر جت: hit به‌علاوهٔ دلیلی که برایٔ نمایشِ صادقِ «چرا نه» به کار می‌رود */
export type JetResult = { hit: boolean; resistance: number | null; reason: string | null };

/**
 * فیلتر جت، عینِ جزوه:
 *   tvol > 3*avg30 && خریدِ حقیقی/معامله >= 1.5 × فروشِ حقیقی/معامله
 *   && pl >= pc && plp > 0 && pl > [ih][2..59].PriceMax
 *
 * مقایسه با **آخرینِ** معامله است نه قیمتِ پایانی: جت یعنی «همین حالا از
 * مقاومت عبور کرده». رأیِ مالکِ ۱۴۰۵-۰۷-۰۳: هیچ گیتِ تعدادِ معاملاتی ندارد.
 */
export function detectJetBreakout(r: MarketRow, lookbackDays: number, minBuyerPower: number,
                                  minVolRatio: number, requireLastAboveClose: boolean,
                                  minChangePct: number): JetResult {
  const close = num(r.p_closing);
  const last = num(r.p_last);
  if (close == null || close <= 0) return { hit: false, resistance: null, reason: 'قیمت پایانی ندارد' };
  if (last == null) return { hit: false, resistance: null, reason: 'آخرین معامله ندارد' };

  const mult = volumeMultiple(r.tvol, r.month_avg_vol);
  if (mult == null) return { hit: false, resistance: null, reason: 'میانگین حجم ۳۰ روزه ندارد' };
  if (minVolRatio > 0 && mult <= minVolRatio) {
    return { hit: false, resistance: null, reason: 'حجم کمتر از آستانه' };
  }

  const power = r.buyer_power_raw != null ? num(r.buyer_power_raw)
    : buyerPowerRatio(r.buy_i_vol, r.buy_count_i, r.sell_i_vol, r.sell_count_i);
  if (power == null) return { hit: false, resistance: null, reason: 'قدرت خریدار قابل محاسبه نیست' };
  if (power < minBuyerPower) return { hit: false, resistance: null, reason: 'قدرت خریدار زیر آستانه' };

  if (requireLastAboveClose && last < close) return { hit: false, resistance: null, reason: 'آخرین زیر پایانی' };
  const chg = num(r.percent_change);
  if (chg == null || chg <= 0) return { hit: false, resistance: null, reason: 'درصد تغییر مثبت نیست' };
  if (chg < minChangePct) return { hit: false, resistance: null, reason: 'درصد تغییر زیر آستانه' };

  const resistance = resistanceLadderHigh(r, lookbackDays);
  if (resistance == null) return { hit: false, resistance: null, reason: 'تاریخچهٔ کاملِ پلکان مقاومت را ندارد' };
  if (last <= resistance) return { hit: false, resistance, reason: 'آخرین هنوز زیر مقاومت است' };
  return { hit: true, resistance, reason: null };
}
