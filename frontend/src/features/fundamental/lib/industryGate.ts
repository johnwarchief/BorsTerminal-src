// features/fundamental/lib/industryGate.ts -- وضعیت گیت صنعت/نرخ‌گذاری (شاخص ۵)
// یک منبع واحد برای رنگ و متن در «کارت FTS»، «drill-down شاخص ۵» و
// «دروازه‌های ریسک» تا کاربر سه جا یک چیز را ببیند (قبلاً کارت «قبول» سبز
// می‌زد ولی دروازه‌ها «صنعت: neutral» — ناسازگار به نظر می‌رسید).
export type IndustryGateTone = 'green' | 'yellow' | 'red' | 'gray';

/** رژیم‌های قیمت‌گذاری بک‌اند: free | mandatory | neutral */
export function industryGateTone(mode: string | null | undefined): IndustryGateTone {
  if (mode == null || mode === '') return 'gray';
  if (mode === 'free') return 'green';
  if (mode === 'mandatory') return 'red';
  return 'yellow'; // neutral / مختلط
}

export function industryGateLabel(mode: string | null | undefined): string {
  if (mode == null || mode === '') return 'صنعت نامشخص';
  if (mode === 'free') return 'صنعت آزاد';
  if (mode === 'mandatory') return 'صنعت دستوری';
  return 'صنعت مختلط';
}

/** متن مشترک دروازه‌های ریسک: «صنعت مختلط (neutral)» — از همان برچسب کارت */
export function industryGateDetail(mode: string | null | undefined): string {
  if (mode == null || mode === '') return industryGateLabel(mode);
  return `${industryGateLabel(mode)} (${mode})`;
}

/** وضعیت مجاز/غیرمجاز همین گیت (برای برچسب کارت و دروازه‌ها) */
export function industryGatePassLabel(pass: boolean): string {
  return pass ? 'مجاز در غربالگری' : 'حذف از غربالگری';
}
