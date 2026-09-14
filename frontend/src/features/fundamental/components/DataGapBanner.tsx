// features/fundamental/components/DataGapBanner.tsx -- دلیل و راه نبود داده
// متون خام موتور بک‌اند (fts_engine، annualize و…) هرگز به کاربر نشان
// داده نمی‌شوند — هر شکاف به پیام استاندارد و کاربرپسند ترجمه می‌شود.
import type { FtsCard } from '../api/useFtsCard';

type Gap = NonNullable<FtsCard['data_gaps']>[number];

/** پیام استاندارد کاربرپسند برای هر محور شکاف — به‌جای متن خام موتور */
const GAP_MESSAGES: Record<string, { why: string; fix: string }> = {
  '1a_monetary_growth': {
    why: 'گزارش فروش دورهٔ مشابه سال قبل در کدال موجود نیست؛ رشد سالانه هنوز قابل محاسبه نیست.',
    fix: 'با انتشار گزارش ماهانهٔ بعدی یا همگام‌سازی کدال، این شکاف بسته می‌شود.',
  },
  '1b_volume_growth': {
    why: 'ستون تناژ/حجم فیزیکی در گزارش ماهانهٔ کدال ثبت نشده است.',
    fix: 'تا انتشار ستون فیزیکی توسط بک‌اند، رشد واقعی با تعدیل تورمی تخمین زده می‌شود.',
  },
  '2_eps_trend': {
    why: 'سابقهٔ EPS این نماد برای قضاوت سه‌ساله کامل نیست.',
    fix: 'با انتشار صورت‌های سالانهٔ قدیمی‌تر (همگام‌سازی کدال) یا صورت ۱۲ماههٔ سال جاری، داوری قطعی می‌شود.',
  },
  '3_gross_margin': {
    why: 'سود ناخالصِ ثبت‌شده برای این نماد موجود نیست.',
    fix: 'با انتشار صورت سود و زیان سالانه، حاشیه محاسبه می‌شود.',
  },
  '4_sales_to_mcap': {
    why: 'گزارش‌های ماهانهٔ کدال برای سالانه‌سازی فروش کافی نیست؛ فروش سالانهٔ صورت مالی جانشین شد.',
    fix: 'گزارش‌های ماهانهٔ کامل همان سال مالی این شکاف را می‌بندد.',
  },
  '5_industry': {
    why: 'گروه صنعتی این نماد در جدول رژیم قیمت‌گذاری تعریف نشده است.',
    fix: 'بررسی دستی چشم‌انداز صنعت توصیه می‌شود.',
  },
};

/** نگاشت محور به پیام — هم کلید محور (4_sales_to_mcap) هم عدد فارسی («۴») */
const AXIS_TO_KEY: Record<string, keyof typeof GAP_MESSAGES> = {
  '1a_monetary_growth': '1a_monetary_growth',
  '1b_volume_growth': '1b_volume_growth',
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

function standardize(g: Gap): { layer: string; why: string; fix: string } {
  const key = g.axis != null ? AXIS_TO_KEY[g.axis] : AXIS_TO_KEY[g.layer];
  const std = key != null ? GAP_MESSAGES[key] : null;
  return {
    layer: g.layer,
    why: std?.why ?? 'برای این شاخص، دادهٔ کافی در کدال موجود نیست.',
    fix: std?.fix ?? 'با همگام‌سازی بعدی کدال، این شکاف ممکن است بسته شود.',
  };
}

export function DataGapBanner({ gaps }: { gaps: NonNullable<FtsCard['data_gaps']> }) {
  if (!gaps || gaps.length === 0) return null;
  const items = gaps.map(standardize);
  return (
    <div className="rounded-2xl border border-accent-yellow/40 bg-accent-yellow/10 p-4" data-testid="data-gap-banner">
      <h3 className="mb-2 text-sm font-black text-accent-yellow">شکاف داده ({items.length})</h3>
      <ul className="flex flex-col gap-2">
        {items.map((g, i) => (
          <li key={`${g.layer}-${i}`} className="text-xs text-text-primary" title={`${g.why} — راه‌حل: ${g.fix}`} data-testid="data-gap-item">
            <span className="font-bold">شاخص {g.layer}: </span>
            {g.why} <span className="text-text-secondary">راه‌حل: {g.fix}</span>
            <span aria-hidden className="text-[9px] leading-none text-text-muted"> ⓘ</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
