// features/master/lib/fmtNum.ts -- فرمت‌کنندهٔ اعداد تب ایجنت ارشد
// قاعده: هیچ عدد خامی با اعشار طولانی نمایش داده نمی‌شود.
//   fa0 → عدد صحیح (قیمت/تومان/تعداد برگه/نمره)
//   fa1 → یک رقم اعشار (مضرب حجم/نسبت/درصد/RSI)
//   fa2 → دو رقم اعشار فقط برای مقادیر ظریف با کوتاه‌سازی
import { toFaDigits } from '@shared/lib/fmt';

/** سرمایهٔ فرضی پیش‌فرض ماشین‌حساب پله‌ها (تومان) — قابل ویرایش آنی در همان اینپوت */
export const DEFAULT_ASSUMED_CAPITAL = 100_000_000;

export function fa0(x: number | null | undefined): string {
  if (x == null || !Number.isFinite(x)) return 'بدون داده';
  const grouped = Math.round(x).toString().replace(/\B(?=(\d{3})+(?!\d))/g, '٬');
  return toFaDigits(grouped);
}

export function fa1(x: number | null | undefined): string {
  if (x == null || !Number.isFinite(x)) return 'بدون داده';
  return toFaDigits(Number(x).toFixed(1));
}

export function fa2(x: number | null | undefined): string {
  if (x == null || !Number.isFinite(x)) return 'بدون داده';
  return toFaDigits(Number(x).toFixed(2));
}

/** کوتاه‌سازی هر عدد به یک رقم اعشار (برای متن‌های توضیحی) */
export function round1(x: number): number {
  return Math.round(x * 10) / 10;
}
