// features/technical/lib/tvIndicators.ts — ثبتِ اندیکاتورهای آماده روی klinecharts
// لیستِ نام‌ها در tvIndicatorCatalog است (بی‌import به بیرون) تا منو همان لیست را
// بخواند؛ این فایل فقط پکیج را بار می‌کند و ثبت می‌کند. همان مسیرِ tvTools:
// lazy import، ثبت روی همان نمونهٔ klinecharts خودمان، و idempotent.
import { indicators as pkgIndicators } from 'react-klinecharts-ui/extensions';

import { TV_INDICATORS } from './tvIndicatorCatalog';

export type { TvIndicator } from './tvIndicatorCatalog';
export { TV_INDICATORS, TV_INDICATOR_NAMES } from './tvIndicatorCatalog';

const byName = new Map<string, unknown>((pkgIndicators as { name: string }[]).map((i) => [i.name, i]));

/** نام‌هایی که بسته واقعاً دارد — بقیه در منو نشان داده نمی‌شوند */
export function availableTvIndicators(): typeof TV_INDICATORS {
  return TV_INDICATORS.filter((i) => byName.has(i.name));
}

/**
 * ثبت اندیکاتورها روی apiِ klinecharts؛ idempotent بر پایهٔ getSupportedIndicators.
 * خروجی: تعدادِ ثبت‌شده.
 */
export function registerTvIndicators(api: {
  registerIndicator: (indicator: unknown) => void;
  getSupportedIndicators?: () => string[];
}): number {
  const have = new Set(api.getSupportedIndicators?.() ?? []);
  let n = 0;
  for (const t of TV_INDICATORS) {
    if (have.has(t.name)) continue;
    const tpl = byName.get(t.name);
    if (tpl == null) continue;
    try {
      api.registerIndicator(tpl);
      n += 1;
    } catch {
      // یک اندیکاتورِ ناسازگار نباید بقیه را متوقف کند
    }
  }
  return n;
}
