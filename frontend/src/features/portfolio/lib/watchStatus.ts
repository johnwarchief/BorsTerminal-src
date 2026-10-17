// features/portfolio/lib/watchStatus.ts — تنها داوریِ «وضعیتِ معاملاتی» و ساعتِ ردیف
//
// پیش از این همین دو تابع درونِ `WatchTable` بودند. خروجیِ دیدهبان (Excel/CSV)
// همان متن را می‌خواهد، و یک تعریفِ دوم یعنی دو داوری درِ یک برنامه — پس تابع‌ها
// عیناً جابه‌جا شدند و حالا جدول، پرونده و خروجی هر سه می‌خوانند.
import type { MarketRow } from '@shared/types/marketRow';

/** وضعیتِ معاملاتیِ canonical — سه حالتِ جدا (P0-3): متوقف ≠ st_title ≠ «موردی ثبت نشده» */
export function statusText(row: MarketRow | null): { text: string; title: string; tone: string } {
  if (row == null) return { text: 'بی‌ردیف', title: 'نماد در ردیف‌های فیدِ تابلو نیست (نام معتبر یا تعطیلِ دائم؟)', tone: 'text-text-muted' };
  if (row.stop_state != null && row.stop_state !== '') {
    return { text: 'متوقف', title: row.stop_reasons ?? row.stop_state, tone: 'text-accent-red' };
  }
  if (row.sup_flag != null && row.sup_flag > 0) {
    return { text: 'زیرِ نظر', title: row.sup_reasons ?? row.sup_title ?? '', tone: 'text-accent-yellow' };
  }
  if (row.st_title || row.st_code) {
    return { text: row.st_title ?? row.st_code ?? '', title: row.st_title ?? '', tone: 'text-text-secondary' };
  }
  return { text: 'موردی ثبت نشده', title: 'هیچ وضعیتِ رسمی‌ای برایِ این نماد ثبت نشده است — «سالم» جا نمی‌زند', tone: 'text-text-muted' };
}

/** 122959 → «۱۲:۲۹»؛ نبودِ ساعت «—» است، نه «۰۰:۰۰» */
export function hhmm(h: number | null | undefined): string {
  if (typeof h !== 'number' || !Number.isFinite(h) || h <= 0) return '—';
  const s = String(Math.floor(h)).padStart(6, '0');
  return `${s.slice(0, 2)}:${s.slice(2, 4)}`;
}
