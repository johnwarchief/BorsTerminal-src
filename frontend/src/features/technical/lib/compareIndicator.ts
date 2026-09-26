// features/technical/lib/compareIndicator.ts -- مطالعۀ «همسنج» روی klinecharts v10
// دو خط روی یک مقیاسِ ۱۰۰: این نماد و نمادِ همسنج. سری را compareSeries می‌سازد
// و همین‌جا فقط ثبت می‌شود؛ هیچ عددی درcalc ساختگی نیست.
import type { CompareRow } from './compareSeries';

export const COMPARE_INDICATOR = 'NN_COMPARE';
export const COMPARE_PANE_ID = 'sub_pane_compare';

/**
 * تنها جایِ نگهداریِ سری. calc موتور همین را می‌خواند؛ وقتی ردیف‌ها عوض
 * می‌شوند چارت باید مطالعه را از نو بسازد (overrideIndicator محاسبه را
 * دوباره اجرا نمی‌کند مگر calcParams عوض شود).
 */
const holder: { rows: CompareRow[] } = { rows: [] };

export function setCompareRows(rows: readonly CompareRow[]): void {
  holder.rows = rows.map((r) => ({ self: r.self, other: r.other }));
}

export function getCompareRows(): readonly CompareRow[] {
  return holder.rows;
}

export function registerCompareIndicator(api: {
  registerIndicator: (indicator: unknown) => void;
  getSupportedIndicators?: () => string[];
}): boolean {
  if ((api.getSupportedIndicators?.() ?? []).includes(COMPARE_INDICATOR)) return true;
  try {
    api.registerIndicator({
      name: COMPARE_INDICATOR,
      shortName: 'همسنج',
      series: 'normal',
      // نسخهٔ محاسبه: با هر seriesِ تازه این عدد بالا می‌رود تا calc دوباره اجرا شود
      calcParams: [0],
      precision: 1,
      figures: [
        // در klinecharts v10 فیلدِ stylesِ figure **تابع** است؛ شیءِ ساده باعث
        // «l.call is not a function» می‌شود (هر بار که style صدا زده می‌شود).
        { key: 'self', title: 'این نماد: ', type: 'line', styles: () => ({ color: '#38bdf8', size: 1.5 }) },
        { key: 'other', title: 'همسنج: ', type: 'line', styles: () => ({ color: '#fbbf24', size: 1.5 }) },
      ],
      calc: () => holder.rows.map((r) => ({ self: r.self, other: r.other })),
    });
    return true;
  } catch {
    return false;
  }
}
