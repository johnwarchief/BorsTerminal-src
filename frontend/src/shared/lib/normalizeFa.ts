// shared/lib/normalizeFa.ts -- یکسان‌سازی نوشتار فارسی و عربی برای جستجو و تطبیق نمادها

const FA_AR_DIGITS_MAP: Record<string, string> = {
  '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
  '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
  '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
  '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
};

/**
 * یکسان‌سازی نوشتار فارسی و عربی:
 * - ي / ى عربی -> ی فارسی
 * - ك عربی -> ک فارسی
 * - حذف نیم‌فاصله (‌)، اعراب‌ها و کشیده (تطویل)
 * - یکدست‌سازی ارقام فارسی/عربی به لاتین
 * - حذف فاصله‌های اضافه و تبدیل به حروف کوچک
 */
export function normalizeFa(s: string | null | undefined): string {
  if (!s) return '';
  return String(s)
    .replace(/[ً-ْـ]/g, '') // اعراب و کشیده
    .replace(/[يى]/g, 'ی')   // ي و ى -> ی
    .replace(/\u0643/g, 'ک')           // ك -> ک
    .replace(/[\u200c\u200b\ufeff]/g, '')   // نیم‌فاصله و کاراکترهای صفر-عرض
    .replace(/[۰-۹٠-٩]/g, (d) => FA_AR_DIGITS_MAP[d] ?? d) // ارقام یکدست
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

/**
 * بررسی تطابق زیررشته با پشتیبانی از چندکلمه‌ای و نرمال‌سازی کاراکترها
 */
export function matchFa(source: string | null | undefined, query: string | null | undefined): boolean {
  if (!query || !query.trim()) return true;
  if (!source) return false;
  const nSource = normalizeFa(source);
  const nQuery = normalizeFa(query);
  if (!nQuery) return true;

  // تطابق مستقیم رشته نرمال‌شده
  if (nSource.includes(nQuery)) return true;

  // تطابق تک‌تک کلمات واردشده (مثلاً 'ملی مس' در 'ملی صنایع مس ایران')
  const words = nQuery.split(' ').filter(Boolean);
  if (words.length > 1) {
    return words.every((w) => nSource.includes(w));
  }

  // تطابق بدون فاصله (مثلاً 'فملی2' با 'فملی ۲')
  const noSpaceSource = nSource.replace(/\s+/g, '');
  const noSpaceQuery = nQuery.replace(/\s+/g, '');
  return noSpaceSource.includes(noSpaceQuery);
}
