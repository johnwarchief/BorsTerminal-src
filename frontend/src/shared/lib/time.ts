import { toFaDigits } from './fmt';
// shared/lib/time.ts -- تاریخ جلالی و زمان با Intl (بدون وابستگی اضافه)
const FA_TIME = new Intl.DateTimeFormat('fa-IR', {
  dateStyle: 'medium',
  timeStyle: 'short',
});

const FA_DATE = new Intl.DateTimeFormat('fa-IR', { dateStyle: 'long' });

const FA_CLOCK = new Intl.DateTimeFormat('fa-IR', {
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
});

/** تاریخ و ساعت فارسی از epoch ms */
export function fmtDateTime(ts: number | null | undefined): string {
  if (ts == null || !Number.isFinite(ts)) return '-';
  return FA_TIME.format(new Date(ts));
}

/** فقط تاریخ جلالی */
export function fmtDate(ts: number | null | undefined): string {
  if (ts == null || !Number.isFinite(ts)) return '-';
  return FA_DATE.format(new Date(ts));
}

/** فقط ساعت */
export function fmtClock(ts: number | null | undefined): string {
  if (ts == null || !Number.isFinite(ts)) return '-';
  return FA_CLOCK.format(new Date(ts));
}

/** سن نسبی به فارسی: «3 دقیقه پیش» */
export function fmtAge(ts: number, now = Date.now()): string {
  const d = Math.max(0, now - ts);
  const s = Math.floor(d / 1000);
  if (s < 60) return 'لحظاتی پیش';
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} دقیقه پیش`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} ساعت پیش`;
  const days = Math.floor(h / 24);
  return `${days} روز پیش`;
}

/** «2026-10-16T02:43:50» (ساعتِ ساختِ پاسخ درِ `_stamp()`ِ بک‌اند) → «۰۲:۴۳:۵۰».
 *  بی‌هیچ محاسبه‌ای: همانِ رشته بریده وِ باِ رقمِ فارسی. چرا از `fmtClock(ts)` جدا
 *  می‌ماند: اینِ رشته ساعتِ *همانِ ماشینی* است که سرور روی آن است وِ درِ اپِ رومیزی
 *  سرور وِ کلاینت یک دستگاه‌اند (`MarketStatusPanel` همین فرض را سند کرده)؛ تبدیلش
 *  به epoch اینجا یکِ حدسِ منطقهٔ زمانی اضافه می‌کرد.
 *  null یعنی پاسخ آنِ ستون را نداشته — وِ رابط باید نبودنش را بگوید، نه اینکه
 *  ساعتِ پنلِ همسایه را بهِ آنِ نسبت دهد. */
export function serverStamp(computedAt: string | null | undefined): string | null {
  if (!computedAt) return null;
  const t = computedAt.slice(11, 19);
  return /^\d{2}:\d{2}:\d{2}$/.test(t) ? toFaDigits(t) : null;
}
