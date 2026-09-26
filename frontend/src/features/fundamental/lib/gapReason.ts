// features/fundamental/lib/gapReason.ts -- «علتِ» نبود داده (منبع واحد)
// کاربر برچسب عمومی «شکاف داده» را نمی‌خواهد؛ هر جا داده نیست، همان دلیل
// کوتاهِ قابلفهم نمایش داده میشود و متنِ کامل علت + راهحل در tooltip
// (الگوی GapHint) میآید. بک‌اند علت را خودش می‌داند و آن را می‌فرستد؛ این‌جا
// همان متن پیش‌رویِ متنِ عمومیِ هر محور است و فقط رشته‌های فنیِ درونِ متن
// (نامِ ستون/مسیر API) به متنِ جانشینِ محور تبدیل می‌شوند.
// کلیدها همان محورهای شاخص در `data_gaps[]` و `passes` هستند.
import { toFaDigits } from '@shared/lib/fmt';
import type { FtsCard } from '../api/useFtsCard';

export type GapAxis =
  | '1a_monetary_growth'
  | '1b_volume_growth'
  | '2_eps_trend'
  | '3_gross_margin'
  | '4_sales_to_mcap'
  | '5_industry';

export interface GapReason {
  /** برچسب کوتاهِ علتدار برای سلول/برچسب (جای «شکاف داده») */
  label: string;
  /** علت کامل — tooltip */
  why: string;
  /** راهحل بستن شکاف — tooltip */
  fix: string;
}

/** پیام استاندارد هر محور — برچسب کوتاه + علت + راهحل */
export const GAP_REASONS: Record<GapAxis, GapReason> = {
  '1a_monetary_growth': {
    label: 'گزارش ماهانهٔ کدال نیست',
    why: 'گزارش فروش دورهٔ مشابه سال قبل در کدال موجود نیست؛ رشد سالانه هنوز قابل محاسبه نیست.',
    fix: 'با انتشار گزارش ماهانهٔ بعدی یا همگام‌سازی کدال، این شکاف بسته می‌شود.',
  },
  '1b_volume_growth': {
    label: 'گزارش مقداری در کدال نیست',
    why: 'ستون مقدار و حجم فیزیکی در گزارش ماهانهٔ کدال ثبت نشده است.',
    fix: 'تا انتشار ستون مقدار/تناژ در گزارش ماهانهٔ کدال، رشد واقعی با تعدیل تورمی تخمین زده می‌شود.',
  },
  '2_eps_trend': {
    label: 'سابقهٔ EPS کدال کامل نیست',
    why: 'سابقهٔ EPS این نماد برای قضاوت سه‌ساله کامل نیست.',
    fix: 'با انتشار صورت‌های سالانهٔ قدیمی‌تر (همگام‌سازی کدال) یا صورت ۱۲ماههٔ سال جاری، داوری قطعی می‌شود.',
  },
  '3_gross_margin': {
    label: 'سود ناخالص در کدال نیست',
    why: 'سود ناخالصِ ثبت‌شده برای این نماد موجود نیست.',
    fix: 'با انتشار صورت سود و زیان سالانه، حاشیه محاسبه می‌شود.',
  },
  '4_sales_to_mcap': {
    label: 'سالانه‌سازی فروش کدال ناقص',
    why: 'گزارش‌های ماهانهٔ کدال برای سالانه‌سازی فروش کافی نیست؛ فروش سالانهٔ صورت مالی جانشین شد.',
    fix: 'گزارش‌های ماهانهٔ کامل همان سال مالی این شکاف را می‌بندد.',
  },
  '5_industry': {
    label: 'صنعت در جدول قیمت‌گذاری نیست',
    why: 'گروه صنعتی این نماد در جدول رژیم قیمت‌گذاری تعریف نشده است.',
    fix: 'با ثبت گروه صنعتی این نماد در جدول قیمت‌گذاری، شاخص ۵ داوری می‌شود.',
  },
};

/** وقتی محور/علت مشخص نیست — متن جانشین باید خودش گویا باشد، نه برچسب خالی */
export const GAP_FALLBACK: GapReason = {
  label: 'گزارش کدال ناقص است',
  why: 'دادهٔ کافی در کدال موجود نیست.',
  fix: 'با همگام‌سازی بعدی کدال، این شکاف ممکن است بسته شود.',
};

/** علت‌های متغیربه‌متغیرِ فرمول‌ها (شاخص ۴ و مانند آن) */
export const NO_ANNUAL_SALES = 'فروش سالانه‌شده در دسترس نیست';
export const NO_GROSS_MARGIN = 'حاشیهٔ ناخالص ثبت نشده';
export const NO_MCAP = 'ارزش بازار در دسترس نیست';
export const NOT_COMPUTABLE = 'خروجی قابل محاسبه نیست';

/** نگاشت محور به کلید — هم کلید محور (4_sales_to_mcap) هم عدد فارسی («۴») */
export const AXIS_TO_KEY: Record<string, GapAxis> = {
  '1a_monetary_growth': '1a_monetary_growth',
  '1b_volume_growth': '1b_volume_growth',
  // بک‌اند این محور را `1b_physical_volume` می‌فرستد (v10_data_gaps). بی‌این
  // هم‌نامی، شکاف ۱ب به جای علتِ واقعی‌اش به برچسبِ عمومیِ fallback می‌افتاد.
  '1b_physical_volume': '1b_volume_growth',
  '2_eps_trend': '2_eps_trend',
  '3_gross_margin': '3_gross_margin',
  '4_sales_to_mcap': '4_sales_to_mcap',
  '5_industry': '5_industry',
  '۱الف': '1a_monetary_growth',
  '۱ب': '1b_volume_growth',
  '۲': '2_eps_trend',
  '۳': '3_gross_margin',
  '۴': '4_sales_to_mcap',
  '۵': '5_industry',
  '1': '1a_monetary_growth',
  '2': '2_eps_trend',
  '3': '3_gross_margin',
  '4': '4_sales_to_mcap',
  '5': '5_industry',
};

/** علت کامل یک محور/لایه — با متن جانشینِ گویا اگر ناشناس بود */
export function gapReason(axis?: string | null): GapReason {
  if (axis == null) return GAP_FALLBACK;
  const key = AXIS_TO_KEY[axis];
  return key != null ? GAP_REASONS[key] : GAP_FALLBACK;
}

/** برچسب کوتاه علت — همان چیزی که جای «شکاف داده» مینشیند */
export function gapLabel(axis?: string | null): string {
  return gapReason(axis).label;
}

/** متن tooltip: علت + راه‌حل (یکدست در کل ویژگی) */
export function gapTooltip(axis?: string | null): string {
  const r = gapReason(axis);
  return `${r.why} — راه‌حل: ${r.fix}`;
}

type Gap = NonNullable<FtsCard['data_gaps']>[number];

/** علت‌های بک‌اند که «متنِ آمادهٔ کاربر» نیستند و نباید عیناً نمایش داده شوند.
 *  اینها نامِ ستون، مسیرِ API یا نامِ تابع در خودِ متن دارند. */
const RAW_MARKERS = /api\/|\.json|monthly_sales|fts_engine|annualize|None|NaN/i;

/** نگاشت ردیفِ شکافِ بک‌اند → علت + راه‌حلِ کاربرپسند.
 *  اولویت با متنِ خودِ بک‌اند است: او می‌داند چرا عدد نیست (مثلاً «سطر بهای
 *  تمام‌شده در صورتِ مالیِ ۱۴۰۳ نیست» در برابر «صورتِ سالانه همگام نشده») و
 *  متنِ عمومیِ هر محور فقط جانشینِ آن است، نه جایگزینش. */
export function standardizeGap(g: Gap): { layer: string; why: string; fix: string; label: string } {
  const r = gapReason(g.axis != null ? g.axis : g.layer);
  const why = typeof g.why === 'string' && g.why.trim() && !RAW_MARKERS.test(g.why)
    ? g.why.trim() : r.why;
  const fix = typeof g.fix === 'string' && g.fix.trim() && !RAW_MARKERS.test(g.fix)
    ? g.fix.trim() : r.fix;
  // متنِ بک‌اند تاریخِ میلادی/لاتین دارد («۱۴۰۳/۱۲/۳۰» نه «1403/12/30»)؛
  // تبدیلِ رقم در لایهٔ نمایش است نه داوری، و در یکجا انجام می‌شود.
  return { layer: toFaDigits(g.layer), why: toFaDigits(why), fix: toFaDigits(fix),
           label: toFaDigits(r.label) };
}
