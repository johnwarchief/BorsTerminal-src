// features/market/lib/assetType.ts -- طبقه بندی نوع دارایی (پورت منطق app.js)
// ترتیب شاخه ها مهم است: از خاص به عام. خروجی 11 نوع + برچسب فارسی.
export const ASSET_TYPES = [
  'stock',
  'payeh',
  'option',
  'fund',
  'bond',
  'right',
  'teseh',
  'tal',
  'ati',
  'kala',
  'energy',
] as const;

export type AssetType = (typeof ASSET_TYPES)[number];

/**
 * لایهٔ نمایش/TSETMC: نام مقصد استاندارد TSETMC برای همان ۱۱ کلید داخلی.
 * هیچ map جدیدی لازم نیست -- کلیدها خودِ ۱۱‌گانه‌اند؛ این alias فقط برای
 * خوانایی تایپ در کامپوننت‌های نمایشی است و منطق classify را تغییر نمی‌دهد.
 */
export type TSETMCAssetType = AssetType;

export const ASSET_LABELS: Record<AssetType, string> = {
  stock: 'سهام',
  payeh: 'فرابورس - بازار پایه',
  option: 'اختیار معامله',
  fund: 'صندوق سرمایه‌گذاری',
  bond: 'اوراق بدهی',
  right: 'حق تقدم',
  teseh: 'تسهیلات مسکن',
  tal: 'معاملات پایانی TAL',
  ati: 'آتی',
  kala: 'بورس کالا',
  energy: 'انرژی',
};

type Classifiable = { symbol?: string | null; name?: string | null; sector_name?: string | null; board?: number | string | null };

// حذف نیم فاصله داده ورودی در زمان اجرا با کد نویسه تا متن فایل پاک بماند
const ZWNJ_RE = new RegExp(String.fromCharCode(0x200c), 'g');

function norm(s: string | null | undefined): string {
  return (s ?? '').replace(ZWNJ_RE, '').replace(/ي/g, 'ی');
}

export function classifyAssetType(d: Classifiable): AssetType {
  const name = norm(d.name);
  const sym = norm(d.symbol).toUpperCase();
  const sec = norm(d.sector_name);

  if (sym.startsWith('ض') || (sym.startsWith('ط') && !sym.startsWith('طال'))) return 'option';
  if (name.includes('صندوق') || name.includes('ETF') || sec.includes('صندوق سرمايه')) return 'fund';
  if (
    sym.startsWith('اخزا') ||
    sym.startsWith('اراد') ||
    sym.startsWith('افاد') ||
    sym.startsWith('گام') ||
    name.includes('اوراق') ||
    name.includes('اسناد') ||
    sec.includes('اوراق تامين')
  )
    return 'bond';
  if (sym.endsWith('ح') || name.includes('حق تقدم')) return 'right';
  if (sym.startsWith('تسه') || sym.startsWith('تملی') || name.includes('تسهیلات')) return 'teseh';
  if (sym.startsWith('طال') || sym.includes('TAL')) return 'tal';
  if (name.includes('آتی') && /[0-9]$/.test(sym)) return 'ati';
  if (sec.includes('کالا') || sym.includes('سلف') || name.includes('سلف')) return 'kala';
  if (sec.includes('انرژی') || sec.includes('برق') || name.includes('انرژی')) return 'energy';
  if (Number(d.board) === 2) return 'payeh';
  return 'stock';
}
