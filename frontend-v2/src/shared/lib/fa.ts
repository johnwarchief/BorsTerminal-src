/** اعداد و واحدها — ارقامِ فارسی فقط از همین‌جا؛ هرگز رقمِ دست‌نویس در JSX. */
const FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹';

export function toFaDigits(value: string | number): string {
  return String(value).replace(/[0-9]/g, (d) => FA_DIGITS[Number(d)]);
}

export function fmtInt(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return toFaDigits(Math.round(value).toLocaleString('en-US'));
}

/** ۲ رقم اعشار با ارقامِ فارسی؛ عددِ نامعتبر «—» */
export function fmt2(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return toFaDigits(Math.abs(value).toFixed(2));
}

/** درصد با علامت؛ منبعِ درصد یعنی خودِ تغییر، نه قدرمطلق */
export function fmtPct(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—';
  const sign = value > 0 ? '+' : value < 0 ? '−' : '';
  return sign + toFaDigits(Math.abs(value).toFixed(2)) + '٪';
}

/** هر همت = 10^13 ریال — همان قراردادِ fmt.ts اپِ فعلی */
export const HEMMAT_RIAL = 1e13;

export function toHemmat(rial: number | null | undefined): number | null {
  if (rial == null || !Number.isFinite(rial)) return null;
  return rial / HEMMAT_RIAL;
}

export function fmtHemmat(rial: number | null | undefined): string {
  const h = toHemmat(rial);
  if (h == null) return '—';
  return toFaDigits(h.toFixed(2));
}

/** درصدِ تغییر: فیلدِ صریح، وگرنه از قیمتِ دیروز — هیچ‌وقت صفرِ ساختگی */
export function changePct(
  percentChange: number | null | undefined,
  priceChange: number | null | undefined,
  priceYesterday: number | null | undefined,
): number | null {
  if (percentChange != null && Number.isFinite(percentChange)) return percentChange;
  if (priceChange == null || priceYesterday == null || priceYesterday === 0) return null;
  return (priceChange / priceYesterday) * 100;
}

/** پرچمِ بولین ممکن است boolean، 0/1، یا رشته باشد — همان معنای «فعال» */
export function isOn(value: unknown): boolean {
  return value === true || value === 1 || value === '1';
}

/** سهمِ درصدی (بدونِ علامت) — برای ستون‌هایی مثلِ خریدِ حقیقی */
export function fmtShare(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return toFaDigits(value.toFixed(1)) + '٪';
}
