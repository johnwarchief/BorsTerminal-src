/**
 * model/patterns/labels.ts
 *
 * برچسب‌های فارسیِ مشترکِ الگوهای کلاسیک.
 * تب «الگوها» و overlay چارت هر دو از این‌جا می‌خوانند تا نام‌ها یک‌جا بمانند.
 */
import type { PatternDirection } from './types';

export const KIND_FA: Record<string, string> = {
  FLAG_BULL: 'پرچم صعودی', FLAG_BEAR: 'پرچم نزولی', PENNANT: 'پنانت',
  TRIANGLE_ASC: 'مثلث صعودی', TRIANGLE_DESC: 'مثلث نزولی', TRIANGLE_SYM: 'مثلث متقارن',
  RECTANGLE: 'مستطیل', WEDGE_RISING: 'گُوهٔ صعودی', WEDGE_FALLING: 'گُوهٔ نزولی',
  HEAD_SHOULDERS: 'سر و شانه', INVERSE_HEAD_SHOULDERS: 'سر و شانهٔ معکوس',
  TRIPLE_TOP: 'سه‌قلوی سقف', TRIPLE_BOTTOM: 'سه‌قلوی کف',
  DOUBLE_TOP: 'سقف دوقلو', DOUBLE_BOTTOM: 'کف دوقلو',
};

export const DIRECTION_FA: Record<PatternDirection, string> = {
  bullish: 'صعودی',
  bearish: 'نزولی',
  neutral: 'خنثی',
};
