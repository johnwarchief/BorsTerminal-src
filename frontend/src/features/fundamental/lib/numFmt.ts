// features/fundamental/lib/numFmt.ts -- قالب‌بندی عددیِ خوانا برای جدول غربالگری
// مشکلاتی که این فایل رفع می‌کند (F-10):
//  ۱) fmtPct جداکنندهٔ هزارگان ندارد ⇒ «۳۸۸۵۹۹۰۰۰۰.۰٪» ستون را می‌شکند.
//  ۲) بعضی مقادیر کدال غیرمعقول‌اند (مثلاً رشد ۳٬۸۸۵٬۹۹۰٬۰۰۰٪ یا حاشیهٔ ۱۸۸۵٪-)؛
//     عدد را حذف/گرد نمی‌کنیم (Circuit Breaker) بلکه همان عدد را با نشان هشدار نشان می‌دهیم.
import { toFaDigits } from '@shared/lib/fmt';

/** آستانهٔ «عدد غیرمعقول» — احتمال خطای مبنا/واحدِ دادهٔ کدال */
export const ABSURD_PCT = 1000;

/** درصد با جداکنندهٔ هزارگان و ۱ رقم اعشار (پیش‌فرض) */
export function fmtPctGrouped(x: number | null | undefined, digits = 1): string | null {
  if (x == null || !Number.isFinite(x)) return null;
  const [int, frac] = x.toFixed(digits).split('.');
  const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, '٬');
  const body = frac && Number(frac) !== 0 ? `${grouped}.${frac}` : grouped;
  return toFaDigits(body) + '٪';
}

/** نسبت (×) با جداکنندهٔ هزارگان — برای نسبت فروش/ارزش بازار */
export function fmtRatioGrouped(x: number | null | undefined): string | null {
  if (x == null || !Number.isFinite(x)) return null;
  const [int, frac] = x.toFixed(2).split('.');
  const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, '٬');
  const body = Number(frac) === 0 ? grouped : `${grouped}.${frac}`;
  return toFaDigits(body) + '×';
}

/** آیا این درصد غیرمعقول است؟ (فقط برای نشان‌دادن هشدار، نه حذف مقدار) */
export function isAbsurdPct(x: number | null | undefined): boolean {
  return x != null && Number.isFinite(x) && Math.abs(x) >= ABSURD_PCT;
}

/** توضیح هشدار روی همان عدد — صادقانه: دادهٔ ما مشکوک است، عدد حذف نمی‌شود */
export function absurdHint(x: number | null | undefined): string | null {
  if (!isAbsurdPct(x)) return null;
  return `مقدار غیرمعقول (${fmtPctGrouped(x, 0)} در برابر آستانهٔ ${toFaDigits(ABSURD_PCT)}٪) — احتمال خطای مبنا/واحد در گزارش کدال؛ عدد را دست‌کاری نکرده‌ایم، برای داوری به کارت نماد نگاه کنید.`;
}
