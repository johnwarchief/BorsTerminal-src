// features/market/lib/tapeMath.ts -- ریاضیات خالص تابلوخوانی
// آینهٔ منطقیِ tape_flags.py (بک‌اند) برایِ فیلترهایِ پنج‌گانهٔ تابلو. همه
// توابع خالص‌اند و null را امن برمی‌گردانند: **نبودنِ داده هیچ‌وقت «قبول»
// نیست** و هیچ دروازهِ‌ای با صفرِ جعلی باز نمی‌شود.
//
// مبنایِ حجم درِ پنج فیلتر، ستونِ `vol_ratio_file` است (مقال: Σ[ih][0..29]/30)،
// نه `month_avg_vol`. `volumeMultiple` فقط برایِ نمایشِ «نسبت به میانگین ماه»
// می‌ماند؛ جابه‌جا شدنِ یکی به جای دیگری همان خطایی است که کد و فیلترنویسِ
// TSETMC را از هم دور می‌کرد (رأیِ ۱۸).
import type { MarketRow } from '@shared/types/marketRow';

/** شکاف الگوی ساعت: آخرین دست کم ۲ درصد بالاتر از پایانی (فایل: pl >= pc*1.02) */
export const CLOCK_GAP = 0.02;
/** حد نصاب تعداد معاملات برای الگوی ساعت (فایل: z_tot_tran > 30) */
export const CLOCK_MIN_TRADES = 30;
/** ضریب حجم مشکوک (فایل: tvol > 3*Σ[ih][0..29]/30 و tno > 50) */
export const SUSP_VOL_MULT = 3;
export const SUSP_MIN_TRADES = 50;
/** سقف نسبت سرانه خرید حقیقی به فروش (فایل: 1.5 ×) */
export const PER_CAPITA_MIN = 1.5;
/** سقف نسبت قدرت خریدار (بک اند: clip بالای 10) */
export const BUYER_POWER_CAP = 10;
/** ضریب حجم فیلتر جت (فایل: tvol > 3*Σ[ih][0..29]/30) */
export const JET_VOL_MULT = 3;
/** حداقل تعداد معاملات جت — فایل دو بار می‌نویسد: ``tno>1 && tno>100``.
 *  رأیِ ۱۸ (۱۴۰۵-۰۷-۰۴): در **فیلترِ تابلو** عینِ فایل برگشت؛ رأیِ ۱۷ فقط
 *  جتِ استراتژیک/سیگنال را بیرونِ آن نگه می‌دارد. */
export const JET_TRADES = 1;
export const JET_MIN_TRADES = 100;
/** کف‌روبی: فایل ``zd1 > 1 && qd1 > 100`` */
export const ROOBI_PREV_DAY_VOL_MIN = 1;
export const ROOBI_PREV_DAY_TRAN_MIN = 100;

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

/** نسبت حجم امروز به میانگین ماهانه — **فقط نمایش**، درِ هیچ فیلتری نیست */
export function volumeMultiple(tvol: number | null | undefined, monthAvg: number | null | undefined): number | null {
  const t = num(tvol);
  const m = num(monthAvg);
  if (t == null || m == null || m <= 0) return null;
  return t / m;
}

/**
 * نسبتِ حجمِ فایل: tvol ÷ میانگینِ حجمِ پنجرۀِ [ih][0..29].
 *
 * بک‌اند آن را در ستونِ `vol_ratio_file` می‌سازد، چون مبنایش به پیشینۀِ نشست‌هایِ
 * کارِ‌کرده نیاز دارد و آن را فقط بانک می‌داند. فایل بر ۳۰ِ ثابت تقسیم می‌کند؛
 * بانکِ ما برایِ نیمیِ تابلو کمتر از ۳۰ نشست دارد، پس بر تعدادِ *موجود* تقسیم
 * می‌شود و زیرِ ۱۰ نشست null می‌ماند — یعنی «سنجیده نمی‌شود»، نه «قبول».
 */
export function filterVolumeRatio(r: { vol_ratio_file?: number | null }): number | null {
  return num(r.vol_ratio_file);
}

export type ClockInput = {
  p_last?: number | null;
  p_closing?: number | null;
  tvol?: number | null;
  month_avg_vol?: number | null;
  vol_ratio_file?: number | null;
  z_tot_tran?: number | null;
};

export type ClockResult = { hit: boolean; gap: number | null };

/** الگوی ساعت، عینِ فایل: ``pl >= pc*1.02 && tvol > Σ[ih][0..29]/30 && tno > 30`` */
export function detectClockPattern(r: ClockInput): ClockResult {
  const gap = clockGap(r.p_last, r.p_closing);
  const mult = filterVolumeRatio(r);
  const n = num(r.z_tot_tran);
  const hit =
    gap != null &&
    gap >= CLOCK_GAP &&
    mult != null &&
    mult > 1.0 &&
    n != null &&
    n > CLOCK_MIN_TRADES;
  return { hit, gap };
}

export type SuspInput = {
  tvol?: number | null;
  month_avg_vol?: number | null;
  vol_ratio_file?: number | null;
  z_tot_tran?: number | null;
};

export type SuspResult = { hit: boolean; multiple: number | null };

/** حجم مشکوک، عینِ فایل: حجمِ بیش از ۳ برابرِ مبنایِ ۳۰ نشست و tno > 50 */
export function detectSuspiciousVolume(r: SuspInput): SuspResult {
  const multiple = filterVolumeRatio(r);
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

/** درگاه‌هایِ فیلتر جت — همان بلوکِ `jet` در TapeFilterConfig */
export type JetGates = {
  lookbackDays: number;
  minBuyerPower: number;
  minVolRatio: number;
  requireLastAboveClose: boolean;
  minChangePct: number;
  minTradeCount: number;
};

/** نتیجهٔ فیلتر جت: hit به‌علاوهٔ دلیلی که برایٔ نمایشِ صادقِ «چرا نه» به کار می‌رود */
export type JetResult = { hit: boolean; resistance: number | null; reason: string | null };

/**
 * فیلتر جت، عینِ فایل:
 *   tvol > 3*Σ[ih][0..29]/30 && خریدِ حقیقی/معامله >= 1.5 × فروشِ حقیقی/معامله
 *   && pl >= pc && plp > 0 && pl > [ih][2..59].PriceMax && tno > 1 && tno > 100
 *
 * مقایسه با **آخرینِ** معامله است نه قیمتِ پایانی: جت یعنی «همین حالا از
 * مقاومت عبور کرده». رأیِ ۱۸ (۱۴۰۵-۰۷-۰۴): درِ فیلترِ تابلو عینِ فایل است، پس
 * ``tno > 100`` برگشت؛ رأیِ ۱۷ فقط جتِ استراتژیک را از آن بیرون نگه داشت.
 */
export function detectJetBreakout(r: MarketRow, g: JetGates): JetResult {
  const fail = (reason: string, resistance: number | null = null): JetResult =>
    ({ hit: false, resistance, reason });

  const close = num(r.p_closing);
  const last = num(r.p_last);
  if (close == null || close <= 0) return fail('قیمت پایانی ندارد');
  if (last == null) return fail('آخرین معامله ندارد');

  const mult = filterVolumeRatio(r);
  if (mult == null) return fail('مبنای حجمِ سی نشستِ کامل را ندارد');
  if (g.minVolRatio > 0 && mult <= g.minVolRatio) return fail('حجم کمتر از آستانه');

  const tno = num(r.z_tot_tran);
  if (tno == null) return fail('تعداد معاملات ندارد');
  if (tno <= JET_TRADES) return fail('تعداد معاملات از ۱ بیشتر نیست');
  if (tno <= g.minTradeCount) return fail('تعداد معاملات زیر آستانهٔ فایل');

  const power = r.buyer_power_raw != null ? num(r.buyer_power_raw)
    : buyerPowerRatio(r.buy_i_vol, r.buy_count_i, r.sell_i_vol, r.sell_count_i);
  if (power == null) return fail('قدرت خریدار قابل محاسبه نیست');
  if (power < g.minBuyerPower) return fail('قدرت خریدار زیر آستانه');

  if (g.requireLastAboveClose && last < close) return fail('آخرین زیر پایانی');
  const chg = num(r.percent_change);
  if (chg == null || chg <= 0) return fail('درصد تغییر مثبت نیست');
  if (chg < g.minChangePct) return fail('درصد تغییر زیر آستانه');

  const resistance = resistanceLadderHigh(r, g.lookbackDays);
  if (resistance == null) return fail('تاریخچهٔ کاملِ پلکان مقاومت را ندارد');
  if (last <= resistance) return fail('آخرین هنوز زیر مقاومت است', resistance);
  return { hit: true, resistance, reason: null };
}
