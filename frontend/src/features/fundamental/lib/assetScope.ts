// features/fundamental/lib/assetScope.ts -- قلمرو غربالگری بنیادی
// جدول غربالگری FTS مختص «شرکت‌های تولیدی و خدماتی» بورس/فرابورس است.
// صندوق‌ها، کارگزاری‌ها، اوراق و مشتقه‌ها به‌صورت پیش‌فرض حذف می‌شوند.
// طبقه‌بندی نوع دارایی از پورت منطق تابلو (features/market/lib/assetType) قرض
// گرفته می‌شود — فقط‌خواندنی import؛ منطق تکراری ساخته نشد.
import { classifyAssetType } from '@features/market/lib/assetType';
import type { FtsScreenRow } from '../api/useFtsScreen';

/** نام‌های دارای «کارگزاری» — سهم رفاهی کارگزاران (گپارس) صندوق/کارگزار نیست */
const BROKER_RE = /کارگزاری|كارگزاری/;

/** آیا این ردیف اصلاً «شرکت» است و جای جدول غربالگری بنیادی را دارد؟ */
export function isFundamentalCompany(row: Pick<FtsScreenRow, 'symbol' | 'name' | 'sector_name'>): boolean {
  const type = classifyAssetType({ symbol: row.symbol, name: row.name, sector_name: row.sector_name });
  if (type !== 'stock') return false;
  // کارگزاری‌ها روی بورس مثل شرکت می‌آیند (نوع دارایی stock) — با نام جدا می‌شوند
  if (BROKER_RE.test(row.name ?? '')) return false;
  return true;
}

export type CompanyClass = 'production' | 'service' | 'financial' | 'holding' | 'other';

/** بخش‌هایی که فیزیکی/تناژ ندارند: خدماتی، مالی/بانکی، بیمه، هلدینگ و سرمایه‌گذاری */
const NON_PHYSICAL_SECTOR_RE =
  /مخابرات|بانك|بانک|بیمه|بيمه|حمل|انبوه|رايانه|فعاليتهاي كمكي|سرمايه گذاريها|سرمايه‌گذاريها|هلدينگ|هلدینگ|سرمايه گذاري |سرمايه‌گذاري /;

/** آیا رشد فیزیکی/تناژ برای این ردیف اصلاً «قابل اعمال» است؟
 *  هلدینگ و سرمایه‌گذاری: نام؛ خدمات/مالی: گروه صنعت */
export function isPhysicalGrowthApplicable(row: Pick<FtsScreenRow, 'name' | 'sector_name'>): boolean {
  const name = row.name ?? '';
  const sector = row.sector_name ?? '';
  if (/هلدينگ|هلدینگ|سرمايه گذاري|سرمايه‌گذاري|سرمایه‌گذاری|سرمایه گذاری/.test(name)) return false;
  if (NON_PHYSICAL_SECTOR_RE.test(sector)) return false;
  return true;
}

/** برچسب وضعیت ستون رشد فیزیکی برای ردیف‌های غیرتولیدی */
export const PHYSICAL_NA_LABEL = 'N/A';
