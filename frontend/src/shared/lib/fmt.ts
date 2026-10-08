// shared/lib/fmt.ts -- قالب بندی اعداد فارسی و مبالغ
const FA_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];

/** تبدیل ارقام لاتین به فارسی */
export function toFaDigits(input: string | number): string {
  return String(input).replace(/[0-9]/g, (d) => FA_DIGITS[Number(d)]);
}

/** تبدیل ارقام فارسی/عربی به لاتین */
export function toEnDigits(input: string): string {
  return input
    .replace(/[۰-۹]/g, (d) => String(d.charCodeAt(0) - 0x06f0))
    .replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 0x0660));
}

/**
 * خواندنِ عدد از ورودیِ کاربر: با ارقامِ فارسی/عربی، با جداکننده، و با علامتِ منفی.
 * هر چیزِ دیگر null — به‌خصوص ورودیِ خالی که صفر نیست. «صفر» و «ننوشته» دو
 * حالِتِ متفاوت‌اند و هیچ‌وقت نباید یکی جای دیگری را بگیرد.
 */
export function parseNum(raw: string | number | null | undefined): number | null {
  if (typeof raw === 'number') return Number.isFinite(raw) ? raw : null;
  if (typeof raw !== 'string') return null;
  const s = toEnDigits(raw).replace(/[٬,\s]/g, '').replace('٫', '.').trim();
  if (!s || s === '-' || s === '.' || s === '-.') return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

/** عدد با جداکننده هزارگان و ارقام فارسی */
export function fmtInt(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return '-';
  const grouped = Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, '٬');
  return toFaDigits(grouped);
}

/** درصد با یک رقم اعشار */
export function fmtPct(x: number | null | undefined, digits = 1): string {
  if (x == null || !Number.isFinite(x)) return '-';
  return toFaDigits(x.toFixed(digits)) + '٪';
}

/** ریال = 10 ریال؟ نه -- هر تومان 10 ریال است */
export const RIAL_PER_TOMAN = 10;
/** هر همت = 10 به توان 13 ریال */
export const HEMMAT_RIAL = 1e13;

/** مبلغ ریالی به همت با دو رقم اعشار */
export function fmtHemmat(rial: number | null | undefined): string {
  if (rial == null || !Number.isFinite(rial)) return '-';
  return toFaDigits((rial / HEMMAT_RIAL).toFixed(2)) + ' همت';
}

/** ارزش بازار به تومان -- تک منبع از TSETMC */
export function fmtMarketCapToman(toman: number | null | undefined): string {
  if (toman == null || !Number.isFinite(toman)) return '-';
  if (toman >= 1e12) return toFaDigits((toman / 1e12).toFixed(2)) + ' همت';
  if (toman >= 1e9) return toFaDigits((toman / 1e9).toFixed(1)) + ' میلیارد تومان';
  if (toman >= 1e6) return toFaDigits((toman / 1e6).toFixed(1)) + ' میلیون تومان';
  return fmtInt(toman) + ' تومان';
}

/** ریال → میلیارد ریال (q_tot_cap درِ بانک ریال است؛ همان واحدِ تابلوی TSETMC)
 *  از درونِ `TapeTable.tsx` منتقل شد تا «ارزشِ معاملات» دو جا دو واحد نگیرد. */
export function toBillionRial(rials: number | null | undefined): number | null {
  return typeof rials === 'number' && Number.isFinite(rials) ? rials / 1e9 : null;
}

/** نمایشِ میلیارد ریال: بالای ۱۰۰ بی‌اعشار، زیرش یک اعشار (قاعدۀ ستونِ ارزشِ
 *  تابلو) — یک پیاده‌سازی، هم ردیفِ تابلو هم «در یک نظرة». داده نیست ⇒ «—». */
export function billionRialText(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '-';
  return v >= 100 ? fmtInt(v) : toFaDigits(v.toFixed(1));
}
