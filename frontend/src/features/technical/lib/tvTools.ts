// features/technical/lib/tvTools.ts -- ثبت ابزارهای ترسیم پیشرفتهٔ TradingView (react-klinecharts-ui)
// این بسته OverlayTemplate های آمادهٔ سازگار با klinecharts >=10 می‌دهد. ما فقط تمپلیت‌ها را
// روی «همان نمونهٔ klinecharts خودمان» ثبت می‌کنیم (بدون تعویض provider یا data-loader) تا
// اورلی‌های سفارشی FTS و سوییچ موتور دست‌نخورده بمانند.
// توجه: این ماژول سنگین است و به‌صورت lazy import می‌شود تا چانک صفحهٔ تکنیکال سبک بماند.
import { overlays } from 'react-klinecharts-ui/extensions';
import type { RegisterOverlayDef } from '../../../vendor/klinecharts';
import { TV_OVERLAY_TOOLS } from './tvToolList';

export { TV_OVERLAY_TOOLS, TV_TOOL_NAMES, type TvOverlayTool } from './tvToolList';

/** نگاشت نام به تمپلیت واقعی از بسته (فقط آن‌هایی که بسته دارد) */
export function tvOverlayTemplates(): { name: string; template: unknown }[] {
  const byName = new Map<string, unknown>(overlays.map((o) => [o.name, o] as [string, unknown]));
  const out: { name: string; template: unknown }[] = [];
  for (const t of TV_OVERLAY_TOOLS) {
    const tpl = byName.get(t.name);
    if (tpl != null) out.push({ name: t.name, template: tpl });
  }
  return out;
}

/**
 * ثبت ابزارهای TV روی نمونهٔ klinecharts ما؛ idempotent (بر اساس getSupportedOverlays).
 * خروجی: تعداد ابزارهای ثبت‌شده.
 */
export function registerTvOverlays(api: {
  registerOverlay: (o: RegisterOverlayDef) => void;
  getSupportedOverlays?: () => string[];
}): number {
  const have = new Set(api.getSupportedOverlays?.() ?? []);
  let n = 0;
  for (const { name, template } of tvOverlayTemplates()) {
    if (have.has(name)) continue;
    try {
      api.registerOverlay(template as RegisterOverlayDef);
      n += 1;
    } catch {
      // یک تمپلیت ناسازگار نباید ثبت بقیه را متوقف کند
    }
  }
  return n;
}
