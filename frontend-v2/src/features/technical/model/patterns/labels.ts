/**
 * model/patterns/labels.ts
 *
 * برچسب‌های فارسیِ مشترکِ الگوهای کلاسیک.
 * تب «الگوها» و overlay چارت هر دو از این‌جا می‌خوانند تا نام‌ها یک‌جا بمانند.
 */
import type { FormationEstimate } from '../types';
import type { PatternDirection } from './types';

export const KIND_FA: Record<string, string> = {
  FLAG_BULL: 'پرچم صعودی', FLAG_BEAR: 'پرچم نزولی', PENNANT: 'پنانت',
  TRIANGLE_ASC: 'مثلث صعودی', TRIANGLE_DESC: 'مثلث نزولی', TRIANGLE_SYM: 'مثلث متقارن',
  RECTANGLE: 'مستطیل', WEDGE_RISING: 'گُوهٔ صعودی', WEDGE_FALLING: 'گُوهٔ نزولی',
  HEAD_SHOULDERS: 'سر و شانه', INVERSE_HEAD_SHOULDERS: 'سر و شانهٔ معکوس',
  TRIPLE_TOP: 'سه‌قلوی سقف', TRIPLE_BOTTOM: 'سه‌قلوی کف',
  DOUBLE_TOP: 'سقف دوقلو', DOUBLE_BOTTOM: 'کف دوقلو',
  CUP_HANDLE: 'کاپ‌هندل', INVERSE_CUP_HANDLE: 'کاپ‌هندل معکوس',
  ROUNDING_TOP: 'گردشدن سقف', ROUNDING_BOTTOM: 'گردشدن کف',
  DIAMOND_TOP: 'دیاموند سقف', DIAMOND_BOTTOM: 'دیاموند کف',
  BROADENING_TOP: 'پهن‌شوندهٔ سقف', BROADENING_BOTTOM: 'پهن‌شوندهٔ کف',
  ISLAND_REVERSAL: 'جزیره‌ای', THREE_RISING_PEAKS: 'سه‌قلهٔ صعودی', THREE_FALLING_PEAKS: 'سه‌قلهٔ نزولی',
};

export const DIRECTION_FA: Record<PatternDirection, string> = {
  bullish: 'صعودی',
  bearish: 'نزولی',
  neutral: 'خنثی',
};

/**
 * R-PA-17: تنها دروازهٔ درصد — زیرِ آستانهٔ نمونه، هیچ عددی به UI نمی‌رسد.
 * ورودی همان FormationEstimate (نسبت ۰..۱) است؛ خروجی نسبت یا null.
 */
export function showPercent(
  formation: FormationEstimate | null | undefined,
  minResolved: number,
): number | null {
  if (formation?.probability == null) return null;
  if (formation.resolved < minResolved) return null;
  return formation.probability;
}
