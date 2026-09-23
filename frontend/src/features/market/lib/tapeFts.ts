// features/market/lib/tapeFts.ts -- سنجه‌های FTSِ ست ردیف تابلو + نرمال‌سازی نماد
// مرز (boundaries): market فقط shared/contracts؛ این ماژول کاملاً خالص است و هیچ
// وابستگی‌ای به بک‌اند FTS یا ویژگی دیگری ندارد (فقط tapeMath همان تب).
import { perCapita } from './tapeMath';
import type { MarketRow } from '@shared/types/marketRow';

/** ریال → میلیون تومان: ۱ م.ت = 1e7 ریال (آینهٔ mstat_local_v975: M_TUMAN_FROM_RIAL) */
export const M_TUMAN_FROM_RIAL = 1e7;

/** آستانهٔ «حجم مشکوک FTS»: نسبت حجم به میانگین ماهانه > ۳ برابر */
export const FTS_VOL_RATIO_HOT = 3;

/** کدهای صنعت زیر «وتوی سخت‌گیرانه بیمه» (REJECT_ALL_INSURANCE — سند v2.1) */
export const INSURANCE_TOKENS = ['بیمه', 'بازنشستگی'] as const;

const ZWNJ_RE = new RegExp(String.fromCharCode(0x200c), 'g');

/** نرمال‌سازی نماد/صنعت: عربی→فارسی + حذف نیم‌فاصله + trim (کلید تطبیق با اسکرینر) */
export function normSymbol(s: string | null | undefined): string {
  return (s ?? '')
    .replace(ZWNJ_RE, '')
    .replace(/ك/g, 'ک')
    .replace(/[يى]/g, 'ی')
    .trim();
}

/** سرانه در میلیون تومان: (ارزش ریالی ÷ تعداد) ÷ 1e7؛ دادهٔ ناقص ⇒ null (بدون عدد ساختگی) */
export function perCapitaMt(
  volRial: number | null | undefined,
  count: number | null | undefined,
): number | null {
  const pc = perCapita(volRial, count);
  return pc == null ? null : pc / M_TUMAN_FROM_RIAL;
}

/**
 * قیمت میانگین وزنی (vwap) به ریال — آینهٔ mstat_engine:599.
 * ارزش کل ÷ حجم کل = ریال هر سهم؛ اگر نبود، قیمت پایانی/آخرین.
 */
function vwapRial(r: Partial<Pick<MarketRow, 'q_tot_cap' | 'q_tot_tran' | 'p_closing' | 'p_last'>>): number {
  const cap = r.q_tot_cap;
  const vol = r.q_tot_tran;
  if (cap != null && vol != null && vol > 0) return cap / vol;
  return r.p_closing ?? r.p_last ?? 0;
}

type PerCapitaRow = Partial<
  Pick<MarketRow, 'buy_i_vol' | 'sell_i_vol' | 'buy_count_i' | 'sell_count_i' | 'q_tot_cap' | 'q_tot_tran' | 'p_closing' | 'p_last'>
>;

/**
 * سرانهٔ خرید حقیقی به میلیون تومان — (سهمِ خرید حقیقی ÷ تعدادِ معامله) × vwap ÷ 1e7.
 * آینهٔ mstat_engine pc_buy: buy_i_vol تعدادِ سهم است (نه ریال)، پس یک‌بار و
 * بدون هیچ حدسِ بزرگی، به‌ارزشِ ریالی تبدیل و سپس به م.ت می‌رسد. قیمتِ فاقد/صفر
 * ⇒ null (هرگز عددِ جعلی نه).
 */
export function buyPerCapitaMt(r: PerCapitaRow): number | null {
  const count = r.buy_count_i;
  const vol = r.buy_i_vol;
  if (count == null || count <= 0 || vol == null) return null;
  const price = vwapRial(r);
  if (!(price > 0)) return null;
  return ((vol / count) * price) / M_TUMAN_FROM_RIAL;
}

/** سرانهٔ فروش حقیقی به میلیون تومان — قرینهٔ buyPerCapitaMt (آینهٔ pc_sell). */
export function sellPerCapitaMt(r: PerCapitaRow): number | null {
  const count = r.sell_count_i;
  const vol = r.sell_i_vol;
  if (count == null || count <= 0 || vol == null) return null;
  const price = vwapRial(r);
  if (!(price > 0)) return null;
  return ((vol / count) * price) / M_TUMAN_FROM_RIAL;
}

/** نماد دارای پسوند عددی (عمده/بلوکی/حق‌تقدم غیرعادی) — مبنای فیلتر خودکار تابلو */
export function isNumericSuffixSymbol(symbol: string | null | undefined): boolean {
  return /[0-9۰-۹]$/.test((symbol ?? '').trim());
}

/** فیلتر خودکار: کنار گذاشتن ردیف‌های دارای پسوند عددی */
export function dropNumericSuffixRows(rows: MarketRow[]): MarketRow[] {
  return rows.filter((r) => !isNumericSuffixSymbol(r.symbol));
}

/** آیا صنعت زیر بیمه/بازنشستگی است؟ (وتوی سخت‌گیرانه) */
export function isInsuranceSector(sector: string | null | undefined): boolean {
  const s = normSymbol(sector);
  return s.length > 0 && INSURANCE_TOKENS.some((t) => s.includes(t));
}
