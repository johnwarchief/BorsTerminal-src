/** تاریخِ تابلو (YYYYMMDD میلادی) → رشتهٔ شمسی؛ ورودیِ نامعتبر «—» */
export function jalaliFromYmd(ymd: number | null | undefined): string {
  if (ymd == null || ymd < 19000101) return '—';
  const y = Math.floor(ymd / 10000);
  const m = Math.floor(ymd / 100) % 100;
  const d = ymd % 100;
  if (m < 1 || m > 12 || d < 1 || d > 31) return '—';
  return new Intl.DateTimeFormat('fa-IR-u-ca-persian', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    timeZone: 'UTC',
  }).format(new Date(Date.UTC(y, m - 1, d)));
}
