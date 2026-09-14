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
