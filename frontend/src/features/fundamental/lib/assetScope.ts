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

/** نرمال‌سازی حروف عربی/نیم‌فاصله برای تطبیق نام و صنعت — کدال/TSETMC یک گروه را
 *  با دو املا می‌دهد («سرمايه گذاريها» عربی در برابر «سرمایه‌گذاری‌ها» فارسی) */
export function normalizeFa(s: string | null | undefined): string {
  return String(s ?? '')
    .replace(/\u064a/g, '\u06cc')
    .replace(/\u0643/g, '\u06a9')
    .replace(/\u200c/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

/** بخش‌هایی که فیزیکی/تناژ ندارند: خدماتی، مالی/بانکی، بیمه، هلدینگ و سرمایه‌گذاری */
const NON_PHYSICAL_SECTOR_RE =
  /مخابرات|بانك|بانک|بيمه|بیمه|حمل|انبوه|رايانه|رایانه|فعاليتهاي كمكي|فعالیتهای کمکی|سرمايه گذاريها|سرمایه گذاریها|هلدينگ|هلدینگ|سرمايه گذاري |سرمایه گذاری |واسطه گري|واسطهگری|ليزينگ|لیزینگ|بورس|فرابورس|تامين سرمايه|تأمین سرمایه/;

/** شرکت مالی/هلدینگ/سرمایه‌گذاری/بانکی/بیمه/صندوق؟
 *  برای این‌ها «رشد فیزیکی» کاملاً مخفی می‌شود و ارزش‌گذاری NAV لازم است. */
const FINANCIAL_HOLDING_RE =
  /هلدينگ|هلدینگ|سرمايه گذاري|سرمایه گذاري|سرمایه‌گذاری|سرمایه گذاری|واسطه گري|واسطهگری|بانك|بانک|بيمه|بیمه|ليزينگ|لیزینگ|صندوق|تامين سرمايه|تأمین سرمایه/;
export function isFinancialOrHolding(row: Pick<FtsScreenRow, 'name' | 'sector_name'>): boolean {
  const name = normalizeFa(row.name);
  const sector = normalizeFa(row.sector_name);
  return FINANCIAL_HOLDING_RE.test(name) || FINANCIAL_HOLDING_RE.test(sector);
}

/** آیا رشد فیزیکی/تناژ برای این ردیف اصلاً «قابل اعمال» است؟
 *  هلدینگ/سرمایه‌گذاری/مالی/بانکی: هرگز؛ خدمات: گروه صنعت */
export function isPhysicalGrowthApplicable(row: Pick<FtsScreenRow, 'name' | 'sector_name'>): boolean {
  if (isFinancialOrHolding(row)) return false;
  const sector = normalizeFa(row.sector_name);
  if (NON_PHYSICAL_SECTOR_RE.test(sector)) return false;
  return true;
}

/** برچسب وضعیت ستون رشد فیزیکی برای ردیف‌های غیرتولیدی */
export const PHYSICAL_NA_LABEL = 'N/A';
