// features/technical/lib/faLegend.ts — فارسی‌کردنِ سطرِ عنوانِ اندیکاتور روی بوم (#181)
//
// چرا لازم شد: عنوانِ اندیکاتور را خودِ klinecharts از `shortName` و
// `figures[].title` رویِ canvas می‌نویسد، پس هیچ راهِ DOM/CSS ای برایش نیست.
// اندیکاتورهایِ پیش‌فرضِ کتابخانه لاتین‌اند: «VOL» و «MA5: / MA10: / MA20: ».
//
// روش: بعد از هر createIndicator، همان اندیکاتورِ *ساخته‌شده* را
// getIndicators می‌گیریم و فقط `shortName` و `title` را عوض می‌کنیم؛ key و type
// و color خودشان دست‌نخورده می‌مانند. اگر از نو figures بسازیم، ترتیبِ ستون‌ها
// و رنگ‌ها با چیزی که کتابخانه ساخته یکی در نمی‌آید.
import { toFaDigits } from '@shared/lib/fmt';
import type { Chart } from 'klinecharts';
import { MABNA_INDICATORS, TV_INDICATORS } from './tvIndicatorCatalog';

/** نام‌هایِ پیش‌فرضِ klinecharts که در هیچ کاتالوگی نیستند */
const BUILTIN_FA: Record<string, string> = {
  VOL: 'حجم',
  MA: 'میانگین',
  EMA: 'میانگین نمایی',
  RSI: 'قدرت نسبی',
  BOLL: 'بولینگر',
  MACD: 'مک‌دی',
  ST: 'استوکستیک',
};

const CATALOG_FA: Record<string, string> = Object.fromEntries(
  [...TV_INDICATORS, ...MABNA_INDICATORS].map((i) => [i.name, i.label]),
);

/** «MA5: » → «میانگین ۵: » و «VOLUME: » → «حجم: »؛ هر چیزِ ناشناخته همان‌جا می‌ماند */
export function faFigureTitle(title: string): string {
  return title
    .replace(/^MA(\d+)\b/, (_m, n: string) => `میانگین ${toFaDigits(n)}`)
    .replace(/^VOLUME\b/, 'حجم');
}

export function faIndicatorTitle(name: string): string | null {
  return BUILTIN_FA[name] ?? CATALOG_FA[name] ?? null;
}

type LegendChart = Pick<Chart, 'getIndicators' | 'overrideIndicator'>;

/**
 * بعد از createIndicator صدا زده می‌شود. `id` همان شناسهٔ پنل/نمونه است؛ بدونِ
 * آن override رویِ تعریفِ عمومی می‌نشیند و نمونهٔ ساخته‌شده عوض نمی‌شود.
 */
export function persianiseLegend(chart: LegendChart, name: string, id?: string) {
  try {
    const ind = chart.getIndicators({ name })[0];
    if (!ind) return;
    const shortName = faIndicatorTitle(name);
    const figures = (ind.figures ?? []).map((f) => {
      const t = typeof f.title === 'string' ? f.title : null;
      return t ? { ...f, title: faFigureTitle(t) } : f;
    });
    chart.overrideIndicator({ name, ...(id ? { id } : {}), ...(shortName ? { shortName } : {}), figures });
  } catch {
    // موتور هنوز آماده نیست؛ سطرِ عنوانِ لاتین بهتر از چارتِ خراب است
  }
}
