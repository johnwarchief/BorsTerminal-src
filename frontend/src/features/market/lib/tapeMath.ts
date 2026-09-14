// features/market/lib/tapeMath.ts -- ریاضیات خالص تابلوخوانی
// آینه منطق بک اند (api/market.py: f_clock و f_susp و f_jet) برای تست پذیری.
// همه توابع خالص اند و null را امن برمی گردانند.

/** شکاف الگوی ساعت: پایانی دست کم 2 درصد بالاتر از آخرین (بک اند: p_closing >= p_last * 1.02) */
export const CLOCK_GAP = 0.02;
/** حد نصاب تعداد معاملات برای الگوی ساعت (بک اند: z_tot_tran > 30) */
export const CLOCK_MIN_TRADES = 30;
/** ضریب حجم مشکوک (بک اند: tvol > 3 * avg30 و tno > 50) */
export const SUSP_VOL_MULT = 3;
export const SUSP_MIN_TRADES = 50;
/** کف نسبت سرانه خرید حقیقی به فروش (بک اند f_jet: 1.5) */
export const PER_CAPITA_MIN = 1.5;
/** سقف نسبت قدرت خریدار (بک اند: clip بالای 10) */
export const BUYER_POWER_CAP = 10;

function num(v: number | null | undefined): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

/**
 * اختلاف آخرین به پایانی به نسبت پایانی: (pLast - pClosing) / pClosing
 * همان تعریف قرارداد TapePayload.lastVsClose. مقدار منفی یعنی پایانی بالاتر.
 */
export function lastVsClose(pLast: number | null | undefined, pClosing: number | null | undefined): number | null {
  const last = num(pLast);
  const close = num(pClosing);
  if (last == null || close == null || close === 0) return null;
  return (last - close) / close;
}

/**
 * شکاف پایانی به آخرین: (pClosing - pLast) / pLast
 * سمت تشخیص الگوی ساعت در بک اند. مثبت یعنی حمایت پایانی.
 */
export function closingGap(pLast: number | null | undefined, pClosing: number | null | undefined): number | null {
  const last = num(pLast);
  const close = num(pClosing);
  if (last == null || close == null || last === 0) return null;
  return (close - last) / last;
}

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

/** الگوی ساعت: شکاف >= 2 درصد و حجم بالای میانگین و معاملات بالای 30 */
export function detectClockPattern(r: ClockInput): ClockResult {
  const gap = closingGap(r.p_last, r.p_closing);
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
