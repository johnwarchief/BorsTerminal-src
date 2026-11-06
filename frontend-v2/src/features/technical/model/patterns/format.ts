/**
 * frontend-v2/src/features/technical/model/patterns/format.ts
 *
 * قالب‌بندی‌های مشترکِ نمایش الگو: کارت رویداد فعال (ریل) و فید اسکنر
 * هر دو از همین‌جا می‌خوانند تا اعداد و درصدها یک واحد بمانند.
 */
import { toFaDigits } from '@shared/lib/fa';

// R-PAT-24: FormationEstimate احتمال را به‌صورت نسبت ۰..۱ می‌دهد؛ درصد یعنی ×۱۰۰.
// بازهٔ ویلسون هم همان نسبت است، پس سرصفحه و بازه یک واحد دارند.
export const faPct = (rate: number) => `${toFaDigits(Math.round(rate * 100))}٪`;

export const faNum = (value: number | null | undefined, digits = 1) => {
  if (value == null || !Number.isFinite(value)) return '—';
  // Number(...) صفرهای انتهایی را حذف می‌کند تا «۰٫۵» به‌جای «۰٫۵۰» نمایش داده شود.
  return toFaDigits(Number(value.toFixed(digits))).replace('.', '٫');
};

export const faDate = (timestamp: number) => {
  if (!timestamp || !Number.isFinite(timestamp)) return '—';
  try {
    return new Intl.DateTimeFormat('fa-IR-u-ca-persian', {
      month: '2-digit',
      day: '2-digit',
      timeZone: 'UTC',
    }).format(new Date(timestamp));
  } catch {
    return '—';
  }
};
