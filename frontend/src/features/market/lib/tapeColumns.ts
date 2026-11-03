// features/market/lib/tapeColumns.ts -- یکِ مرجعِ ستون/ترتیب برایِ دوِ نما
//
// ردیفِ دسکتاپ (`TapeTable`) وِ کارتِ موبایل (`TapeCards`) همانِ فهرستِ ستون‌ها وِ
// همانِ تابعِ ترتیب را می‌خوانند: اگرِ روزی ستونی اضافه یاِ حذف شود، مرتب‌سازیِ
// گوشی بی‌آنکه کسی بفهمد ازِ ریشه‌اش جدا نمی‌افتد. (رأیِ بندِ ۲.۱ مأموریت:
// «مرتب‌سازی… درِ موبایل درِ دسترس بماند» باِ واژگانِ خودِ تابلو، نه فهرستِ دومی.)
import type { MarketRow } from '@shared/types/marketRow';
import { lastCloseDiff } from './tapePatterns';

export type SortKey =
  | 'symbol'
  | 'p_closing'
  | 'p_last'
  | 'percent_change'
  | 'percent_last'
  | 'tvol'
  | 'z_tot_tran'
  | 'q_tot_cap'
  | 'vol_ratio'
  | 'buyer_power'
  | 'last_vs_close';

/** سرستونِ بی‌مرتب‌سازی (کلیدِ null) — ستونِ بج‌ها عددی نیست که بشود مرتبش کرد */
export const HEADERS: { key: SortKey | null; label: string; hint?: string }[] = [
  // برچسبِ ستون «فیلتر» نیست و فقط خواندنِ سرستون را می‌سازد؛ پس کوتاه‌ترین
  // شکلِ ممکن نوشته می‌شود و نامِ کامل + واحد در title می‌ماند. رویِ
  // نمایشگرِ ۱۳۶۶ این تیترهای بلند در ستونِ ۶۲-۷۸ پیکسلی می‌شکستند و
  // سرستون افقی اسکرول می‌خورد.
  { key: 'symbol', label: 'نماد' },
  { key: 'p_last', label: 'آخرین' },
  { key: 'p_closing', label: 'پایانی', hint: 'قیمت پایانیِ همین روز معاملاتی (p_closing)' },
  // اختلافِ آخرین تا پایانی بغلِ پایانی نشسته (#194): هر دو ستونِ یک مقایسه‌اند
  // — «آخرین» و «پایانی» و «فاصلۀ این دو» — و جدا از هم خوانده نمی‌شوند.
  {
    key: 'last_vs_close',
    label: 'اختلاف٪',
    hint: 'آخرین نسبت به پایانی — منفی یعنی پایانی بالاتر از آخرین، همان شرطِ الگوی ساعت',
  },
  {
    key: 'percent_change',
    label: 'تغییر٪',
    hint: 'پایانی نسبت به دیروز — همان متغیرِ pcp در فیلترنویسیِ TSETMC',
  },
  {
    key: 'percent_last',
    label: 'آخرین٪',
    hint: 'آخرین نسبت به دیروز — همان متغیرِ plp در فیلترنویسیِ TSETMC، و با درصدِ پایانی فرق دارد',
  },
  { key: 'tvol', label: 'حجم' },
  {
    key: 'z_tot_tran',
    label: 'تعداد',
    hint: 'تعدادِ معاملات — همان متغیرِ tno در فیلترنویسیِ TSETMC (z_tot_tran)',
  },
  { key: 'q_tot_cap', label: 'ارزش', hint: 'ارزش معاملات — میلیارد ریال (q_tot_cap)' },
  { key: 'vol_ratio', label: 'حجم/ماه', hint: 'نسبت حجمِ امروز به میانگینِ حجمِ ماه' },
  {
    key: 'buyer_power',
    label: 'خرید / فروش',
    hint:
      'بالا: سرانۀ خرید حقیقی (سبز) و سرانۀ فروش حقیقی (قرمز) به میلیون تومان. ' +
      'پایین: نوارِ سهمِ هر طرف و نسبتِ خرید به فروش',
  },
  {
    key: null,
    label: 'الگو',
    hint: 'برچسبِ الگوهایِ فعال روی همان ردیف: ساعت، حجم مشکوک، جت، کف‌روب، نقطه‌زنی، صف خرید و صف فروش',
  },
];

export const NEG = Number.NEGATIVE_INFINITY;

export function sortVal(r: MarketRow, key: SortKey): number | string {
  switch (key) {
    case 'symbol':
      return r.symbol ?? '';
    case 'p_last':
      return r.p_last ?? NEG;
    case 'p_closing':
      return r.p_closing ?? NEG;
    case 'percent_change':
      return r.percent_change ?? NEG;
    case 'percent_last':
      return r.percent_last ?? NEG;
    case 'tvol':
      return r.tvol ?? NEG;
    case 'z_tot_tran':
      return r.z_tot_tran ?? NEG;
    case 'q_tot_cap':
      return r.q_tot_cap ?? NEG;
    case 'vol_ratio':
      return r.vol_ratio ?? NEG;
    case 'buyer_power':
      return r.buyer_power ?? NEG;
    case 'last_vs_close':
      return lastCloseDiff(r) ?? NEG;
  }
}
