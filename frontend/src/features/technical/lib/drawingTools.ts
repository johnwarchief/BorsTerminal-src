// features/technical/lib/drawingTools.ts -- کاتالوگ ابزارهای ترسیم و نگاشت بر klinecharts v10
// فقط ابزارهایی که نسخهٔ vendor واقعاً پشتیبانی می‌کند نمایش داده می‌شوند
// (getSupportedOverlays). گروه‌بندی بر مبنای docs/CHART-PARITY-REFERENCE.md §۲.

export type DrawingTool = { name: string; label: string };
export type DrawingGroup = { label: string; glyph: string; tools: DrawingTool[] };

export const DRAWING_CATALOG: DrawingGroup[] = [
  {
    label: 'خطوط',
    glyph: '／',
    tools: [
      { name: 'straightLine', label: 'خط روند' },
      { name: 'segment', label: 'پاره‌خط' },
      { name: 'rayLine', label: 'رای' },
      { name: 'horizontalStraightLine', label: 'خط افقی' },
      { name: 'verticalStraightLine', label: 'خط عمودی' },
      { name: 'horizontalRayLine', label: 'رای افقی' },
      { name: 'verticalRayLine', label: 'رای عمودی' },
      { name: 'horizontalSegment', label: 'پاره افقی' },
      { name: 'verticalSegment', label: 'پاره عمودی' },
      { name: 'priceLine', label: 'خط قیمت' },
    ],
  },
  {
    label: 'کانال',
    glyph: '∥',
    tools: [
      { name: 'parallelStraightLine', label: 'کانال موازی' },
      { name: 'priceChannelLine', label: 'کانال قیمت' },
    ],
  },
  {
    label: 'فیبوناچی',
    glyph: 'ف',
    tools: [{ name: 'fibonacciLine', label: 'بازگشتی فیبو' }],
  },
  {
    label: 'حاشیه‌نویسی',
    glyph: 'ت',
    tools: [
      { name: 'simpleAnnotation', label: 'یادداشت' },
      { name: 'simpleTag', label: 'برچسب' },
      { name: 'brush', label: 'قلم' },
    ],
  },
];

/** فقط ابزارهای پشتیبانی‌شدهٔ vendor باقی می‌مانند؛ گروه خالی حذف می‌شود */
export function buildDrawingGroups(supported: string[]): DrawingGroup[] {
  const set = new Set(supported);
  return DRAWING_CATALOG.map((g) => ({ ...g, tools: g.tools.filter((t) => set.has(t.name)) })).filter(
    (g) => g.tools.length > 0,
  );
}
