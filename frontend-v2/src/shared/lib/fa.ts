/** اعداد و واحدها — ارقامِ فارسی فقط از همین‌جا، با جداکنندهٔ هزارگانِ فارسی (٬). */
const nfCache = new Map<number, Intl.NumberFormat>();

function nf(digits: number): Intl.NumberFormat {
  let f = nfCache.get(digits);
  if (!f) {
    f = new Intl.NumberFormat('fa-IR', { maximumFractionDigits: digits, minimumFractionDigits: 0 });
    nfCache.set(digits, f);
  }
  return f;
}

export function faNum(value: number | null | undefined, digits = 0): string {
  if (value == null || !Number.isFinite(Number(value))) return '—';
  return nf(digits).format(Number(value));
}

export const fmtInt = (value: number | null | undefined): string => faNum(value, 0);

const FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹';
export function toFaDigits(value: string | number): string {
  return String(value).replace(/[0-9]/g, (d) => FA_DIGITS[Number(d)]);
}

export function fmtPct(value: number | null | undefined, digits = 2): string {
  if (value == null || !Number.isFinite(Number(value))) return '—';
  const v = Number(value);
  const sign = v > 0 ? '+' : v < 0 ? '−' : '';
  return sign + faNum(Math.abs(v), digits) + '٪';
}

export type Tone = 'up' | 'down' | 'flat';
export function tone(value: number | null | undefined): Tone {
  if (value == null || !Number.isFinite(Number(value))) return 'flat';
  return Number(value) > 0 ? 'up' : Number(value) < 0 ? 'down' : 'flat';
}

export const fmtPrice = (value: number | null | undefined): string =>
  value == null ? '—' : fmtInt(value);

/** ارزش: میلیارد ریال؛ ≥۱۰۰ بدونِ اعشار (هم‌قراردادِ پروتوتایپ) */
export function fmtValue(rial: number | null | undefined): string {
  if (rial == null) return '—';
  const v = rial / 1e9;
  return v >= 100 ? fmtInt(v) : faNum(v, 1);
}

/** ارزشِ بازار: همت (۱۰^۱۳ ریال)، یک رقم اعشار */
export const fmtMcap = (rial: number | null | undefined): string =>
  rial == null ? '—' : faNum(rial / 1e13, 1);

/** حجم: م/هـ مثلِ پروتوتایپ */
export function fmtVolume(value: number | null | undefined): string {
  if (value == null) return '—';
  if (value >= 1e6) return fmtInt(value / 1e6) + ' م';
  if (value >= 1e3) return fmtInt(value / 1e3) + ' هـ';
  return fmtInt(value);
}

export const fmtPe = (value: number | null | undefined): string =>
  value == null ? '—' : value >= 100 ? fmtInt(value) : faNum(value, 1);

export function fmtShare(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return faNum(value, 1) + '٪';
}

/** درصدِ تغییر: فیلدِ صریح، وگرنه از قیمتِ دیروز — بدونِ صفرِ ساختگی */
export function changePct(
  percentChange: number | null | undefined,
  priceChange: number | null | undefined,
  priceYesterday: number | null | undefined,
): number | null {
  if (percentChange != null && Number.isFinite(percentChange)) return percentChange;
  if (priceChange == null || priceYesterday == null || priceYesterday === 0) return null;
  return (priceChange / priceYesterday) * 100;
}

/** پرچم ممکن است boolean، 0/1 یا رشته باشد */
export function isOn(value: unknown): boolean {
  return value === true || value === 1 || value === '1';
}
